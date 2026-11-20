"""Cálculo de los factores del índice de riesgo (RN-01).

Cada factor devuelve un valor normalizado de 0 a 100, donde 0 es ausencia de
riesgo y 100 es riesgo máximo. El índice final es la suma ponderada de esos
valores con los pesos configurados en la tabla `factor_riesgo` (RQF-02).

Las fórmulas son heurísticas y están documentadas a propósito: el enunciado no
pide un modelo predictivo entrenado (RES-02), sino un modelo explicable que el
consejero pueda entender y defender frente al estudiante.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Estudiante, Inasistencia, Matricula, Nota

# Notas: por debajo de esta se considera riesgo máximo; por encima, riesgo nulo.
NOTA_PISO = 1.5
NOTA_TECHO = 3.5
# Inasistencia: a partir de este porcentaje el estudiante pierde la asignatura.
INASISTENCIA_CRITICA = 30.0
# Asignaturas repetidas que se consideran riesgo máximo.
REPETIDAS_CRITICAS = 3


@dataclass
class ValorFactor:
    codigo: str
    nombre: str
    valor: float          # 0 a 100
    peso: float           # 0 a 100
    aporte: float         # valor * peso / 100
    evidencia: str        # texto legible que explica de dónde salió el valor


def _clamp(x: float, bajo: float = 0.0, alto: float = 100.0) -> float:
    return max(bajo, min(alto, x))


def _riesgo_por_nota(promedio: float | None) -> float:
    """Convierte un promedio de 0 a 5 en un valor de riesgo de 0 a 100."""
    if promedio is None:
        return 0.0
    return _clamp((NOTA_TECHO - float(promedio)) / (NOTA_TECHO - NOTA_PISO) * 100)


def factor_rendimiento(db: Session, est: Estudiante, periodo: str, corte: int) -> tuple[float, str]:
    """Promedio de las notas registradas en el corte vigente."""
    promedio = db.scalar(
        select(func.avg(Nota.valor))
        .join(Matricula, Nota.matricula_id == Matricula.id)
        .where(Matricula.estudiante_id == est.id, Matricula.periodo == periodo, Nota.corte == corte)
    )
    if promedio is None:
        return 0.0, "Sin notas registradas en el corte"
    return _riesgo_por_nota(promedio), f"Promedio del corte {corte}: {float(promedio):.2f} / 5,00"


def factor_inasistencia(db: Session, est: Estudiante, periodo: str) -> tuple[float, str]:
    """Porcentaje de inasistencias no justificadas sobre las sesiones programadas."""
    sesiones = db.scalar(
        select(func.sum(Matricula.sesiones_programadas))
        .where(Matricula.estudiante_id == est.id, Matricula.periodo == periodo)
    ) or 0
    if sesiones == 0:
        return 0.0, "Sin sesiones programadas en el periodo"
    faltas = db.scalar(
        select(func.count(Inasistencia.id))
        .join(Matricula, Inasistencia.matricula_id == Matricula.id)
        .where(Matricula.estudiante_id == est.id, Matricula.periodo == periodo,
               Inasistencia.justificada.is_(False))
    ) or 0
    pct = faltas / sesiones * 100
    valor = _clamp(pct / INASISTENCIA_CRITICA * 100)
    return valor, f"Inasistencia del {pct:.0f}% ({faltas} de {sesiones} sesiones)"


def factor_repetidas(db: Session, est: Estudiante, periodo: str) -> tuple[float, str]:
    """Asignaturas que el estudiante está cursando por segunda vez o más."""
    repetidas = db.scalar(
        select(func.count(Matricula.id))
        .where(Matricula.estudiante_id == est.id, Matricula.periodo == periodo,
               Matricula.numero_intento > 1)
    ) or 0
    valor = _clamp(repetidas / REPETIDAS_CRITICAS * 100)
    return valor, f"{repetidas} asignatura(s) repetida(s) en el periodo"


def factor_financiero(est: Estudiante) -> tuple[float, str]:
    """Combinación de apoyo financiero vigente y deuda pendiente."""
    if est.tiene_apoyo_financiero and not est.tiene_deuda_vigente:
        return 0.0, "Con apoyo financiero vigente y sin deuda"
    if est.tiene_apoyo_financiero and est.tiene_deuda_vigente:
        return 40.0, "Con apoyo financiero, pero con deuda pendiente"
    if est.tiene_deuda_vigente:
        return 80.0, "Sin apoyo financiero y con deuda pendiente"
    return 50.0, "Sin apoyo financiero vigente"


def factor_historico(est: Estudiante) -> tuple[float, str]:
    """Promedio acumulado de toda la carrera."""
    valor = _riesgo_por_nota(est.promedio_acumulado)
    return valor, f"Promedio acumulado: {float(est.promedio_acumulado):.2f} / 5,00"


# Mapa código -> función de cálculo. Agregar un factor nuevo al modelo es
# agregar una fila en `factor_riesgo` y una entrada aquí.
CALCULADORES = {
    "RENDIMIENTO": lambda db, est, periodo, corte: factor_rendimiento(db, est, periodo, corte),
    "INASISTENCIA": lambda db, est, periodo, corte: factor_inasistencia(db, est, periodo),
    "REPETIDAS": lambda db, est, periodo, corte: factor_repetidas(db, est, periodo),
    "FINANCIERA": lambda db, est, periodo, corte: factor_financiero(est),
    "HISTORICO": lambda db, est, periodo, corte: factor_historico(est),
}
