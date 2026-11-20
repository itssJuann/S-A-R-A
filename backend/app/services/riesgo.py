"""Motor de riesgo (RQF-05, RQF-06, RN-01, RN-02, RN-03, RN-07)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import UMBRAL_ALTO, UMBRAL_CRITICO, UMBRAL_MEDIO
from ..factores import CALCULADORES, ValorFactor
from ..models import (
    Estudiante, EstadoMatricula, EvaluacionRiesgo, FactorRiesgo, NivelRiesgo,
)

from ..config import CORTE_VIGENTE, PERIODO_VIGENTE  # noqa: F401  (se reexportan)


class ErrorModelo(Exception):
    """El modelo de riesgo está mal configurado."""


def factores_vigentes(db: Session) -> list[FactorRiesgo]:
    factores = list(db.scalars(select(FactorRiesgo).where(FactorRiesgo.vigente.is_(True))))
    if not factores:
        raise ErrorModelo("No hay factores de riesgo vigentes configurados")
    total = round(sum(float(f.peso) for f in factores), 2)
    if total != 100.0:
        raise ErrorModelo(f"Los pesos de los factores vigentes suman {total}%, deben sumar 100%")
    return factores


def clasificar(indice: float) -> NivelRiesgo:
    """RN-02."""
    if indice >= UMBRAL_CRITICO:
        return NivelRiesgo.CRITICO
    if indice >= UMBRAL_ALTO:
        return NivelRiesgo.ALTO
    if indice >= UMBRAL_MEDIO:
        return NivelRiesgo.MEDIO
    return NivelRiesgo.BAJO


def calcular_indice(
    db: Session, estudiante: Estudiante, periodo: str = PERIODO_VIGENTE, corte: int = CORTE_VIGENTE
) -> tuple[float, NivelRiesgo, list[ValorFactor], int]:
    """Calcula el índice sin persistir nada. RN-01."""
    factores = factores_vigentes(db)
    version = max(f.version_modelo for f in factores)
    detalle: list[ValorFactor] = []
    for f in factores:
        calculador = CALCULADORES.get(f.codigo)
        if calculador is None:
            raise ErrorModelo(f"El factor {f.codigo} no tiene una fórmula implementada")
        valor, evidencia = calculador(db, estudiante, periodo, corte)
        peso = float(f.peso)
        detalle.append(ValorFactor(
            codigo=f.codigo, nombre=f.nombre, valor=round(valor, 2), peso=peso,
            aporte=round(valor * peso / 100, 2), evidencia=evidencia,
        ))
    indice = round(sum(d.aporte for d in detalle), 2)
    return indice, clasificar(indice), detalle, version


def evaluar(
    db: Session, estudiante: Estudiante, periodo: str = PERIODO_VIGENTE,
    corte: int = CORTE_VIGENTE, commit: bool = True,
) -> EvaluacionRiesgo:
    """Calcula y guarda una evaluación. RQF-05."""
    indice, nivel, detalle, version = calcular_indice(db, estudiante, periodo, corte)
    evaluacion = EvaluacionRiesgo(
        estudiante_id=estudiante.id,
        indice=indice,
        nivel=nivel,
        detalle_factores=[d.__dict__ for d in detalle],
        version_modelo=version,
        corte=corte,
    )
    db.add(evaluacion)
    db.flush()
    if commit:
        db.commit()
        db.refresh(evaluacion)
    return evaluacion


def evaluar_y_atender(db: Session, estudiante: Estudiante, **kwargs) -> dict:
    """Evalúa y, si corresponde, abre o actualiza el caso de acompañamiento.

    Es el punto de entrada que usan los endpoints de notas e inasistencias (RN-07).
    """
    from . import casos as servicio_casos  # import diferido: evita ciclo

    evaluacion = evaluar(db, estudiante, commit=False, **kwargs)
    resultado = {"evaluacion": evaluacion, "caso": None, "alerta": False, "caso_nuevo": False}
    if evaluacion.nivel in (NivelRiesgo.ALTO, NivelRiesgo.CRITICO):   # RN-03
        resultado["alerta"] = True
        caso, nuevo = servicio_casos.abrir_o_adjuntar(db, estudiante, evaluacion)
        resultado["caso"] = caso
        resultado["caso_nuevo"] = nuevo
    db.commit()
    db.refresh(evaluacion)
    return resultado


def reevaluar_poblacion(db: Session, periodo: str = PERIODO_VIGENTE, corte: int = CORTE_VIGENTE) -> dict:
    """Recálculo masivo al iniciar un corte (RN-07, RQNF-02)."""
    estudiantes = list(db.scalars(
        select(Estudiante).where(Estudiante.estado_matricula == EstadoMatricula.ACTIVA)
    ))
    resumen = {"evaluados": 0, "alertas": 0, "casos_nuevos": 0, "por_nivel": {}}
    for est in estudiantes:
        r = evaluar_y_atender(db, est, periodo=periodo, corte=corte)
        resumen["evaluados"] += 1
        nivel = r["evaluacion"].nivel.value
        resumen["por_nivel"][nivel] = resumen["por_nivel"].get(nivel, 0) + 1
        if r["alerta"]:
            resumen["alertas"] += 1
        if r["caso_nuevo"]:
            resumen["casos_nuevos"] += 1
    return resumen
