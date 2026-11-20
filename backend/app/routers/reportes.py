"""Indicadores de retención (RQF-16)."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..alcance import estudiantes_para_indicadores, programas_para_indicadores
from ..database import get_db
from ..models import (
    CasoAcompanamiento, EstadoCaso, EstadoMatricula, Estudiante, EvaluacionRiesgo,
    NivelRiesgo, Programa, ResultadoCaso, RolNombre, Usuario,
)
from ..schemas import EfectividadNivel, ReporteGeneral
from ..security import exige_rol
from ..services.casos import ESTADOS_ACTIVOS

router = APIRouter(prefix="/api/reportes", tags=["Indicadores"])
direccion = exige_rol(RolNombre.COORDINADOR, RolNombre.BIENESTAR, RolNombre.ADMINISTRADOR)


def _ultimas_evaluaciones(db: Session, permitidos: set[int] | None = None) -> dict[int, EvaluacionRiesgo]:
    """La evaluación más reciente de cada estudiante dentro del alcance."""
    sub = (select(EvaluacionRiesgo.estudiante_id,
                  func.max(EvaluacionRiesgo.id).label("ultimo"))
           .group_by(EvaluacionRiesgo.estudiante_id).subquery())
    q = select(EvaluacionRiesgo).join(sub, EvaluacionRiesgo.id == sub.c.ultimo)
    if permitidos is not None:
        q = q.where(EvaluacionRiesgo.estudiante_id.in_(permitidos))
    return {e.estudiante_id: e for e in db.scalars(q)}


@router.get("/general", response_model=ReporteGeneral, summary="Panel general de retención")
def general(db: Session = Depends(get_db), usuario: Usuario = Depends(direccion)):
    """El coordinador ve los indicadores de su programa; dirección, los de todos."""
    permitidos = estudiantes_para_indicadores(db, usuario)
    evaluaciones = _ultimas_evaluaciones(db, permitidos)
    distribucion = {n: 0 for n in NivelRiesgo}
    for ev in evaluaciones.values():
        distribucion[ev.nivel] += 1
    en_riesgo = distribucion[NivelRiesgo.ALTO] + distribucion[NivelRiesgo.CRITICO]

    def acotar(q):
        return q if permitidos is None else q.where(
            CasoAcompanamiento.estudiante_id.in_(permitidos))

    casos_activos = db.scalar(acotar(select(func.count(CasoAcompanamiento.id))
                              .where(CasoAcompanamiento.estado.in_(ESTADOS_ACTIVOS)))) or 0
    escalados = db.scalar(acotar(select(func.count(CasoAcompanamiento.id))
                          .where(CasoAcompanamiento.escalado.is_(True),
                                 CasoAcompanamiento.estado.in_(ESTADOS_ACTIVOS)))) or 0

    resultados = []
    for r in ResultadoCaso:
        total = db.scalar(acotar(select(func.count(CasoAcompanamiento.id))
                          .where(CasoAcompanamiento.resultado == r))) or 0
        resultados.append({"resultado": r, "cantidad": total})

    retencion, total_act, total_des = [], 0, 0
    visibles = programas_para_indicadores(db, usuario)
    qp = select(Programa).order_by(Programa.nombre)
    if visibles is not None:
        qp = qp.where(Programa.id.in_(visibles))
    for programa in db.scalars(qp):
        activos = db.scalar(select(func.count(Estudiante.id)).where(
            Estudiante.programa_id == programa.id,
            Estudiante.estado_matricula == EstadoMatricula.ACTIVA)) or 0
        desertores = db.scalar(select(func.count(Estudiante.id)).where(
            Estudiante.programa_id == programa.id,
            Estudiante.estado_matricula == EstadoMatricula.RETIRADA)) or 0
        base = activos + desertores
        retencion.append({
            "programa": programa.nombre, "activos": activos, "desertores": desertores,
            "tasa_retencion": round(activos / base * 100, 1) if base else 100.0,
        })
        total_act += activos
        total_des += desertores

    base_global = total_act + total_des
    return {
        "estudiantes_evaluados": len(evaluaciones),
        "en_riesgo": en_riesgo,
        "casos_activos": casos_activos,
        "casos_escalados": escalados,
        "distribucion": [{"nivel": n, "cantidad": c} for n, c in distribucion.items()],
        "resultados": resultados,
        "retencion_por_programa": retencion,
        "tasa_retencion_global": round(total_act / base_global * 100, 1) if base_global else 100.0,
    }


@router.get("/efectividad", response_model=list[EfectividadNivel],
            summary="Efectividad del acompañamiento por nivel de apertura")
def efectividad(db: Session = Depends(get_db), usuario: Usuario = Depends(direccion)):
    """Qué proporción de los casos cerrados terminó en Superado, según el nivel inicial."""
    permitidos = estudiantes_para_indicadores(db, usuario)

    def acotar(q):
        return q if permitidos is None else q.where(
            CasoAcompanamiento.estudiante_id.in_(permitidos))

    salida = []
    for nivel in (NivelRiesgo.ALTO, NivelRiesgo.CRITICO):
        cerrados = db.scalar(acotar(select(func.count(CasoAcompanamiento.id)).where(
            CasoAcompanamiento.nivel_apertura == nivel,
            CasoAcompanamiento.estado == EstadoCaso.CERRADO))) or 0
        superados = db.scalar(acotar(select(func.count(CasoAcompanamiento.id)).where(
            CasoAcompanamiento.nivel_apertura == nivel,
            CasoAcompanamiento.resultado == ResultadoCaso.SUPERADO))) or 0
        salida.append({
            "nivel_apertura": nivel, "cerrados": cerrados, "superados": superados,
            "efectividad": round(superados / cerrados * 100, 1) if cerrados else 0.0,
        })
    return salida
