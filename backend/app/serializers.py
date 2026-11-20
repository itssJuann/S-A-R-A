"""Armado de los DTO que necesitan datos de varias tablas."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    CasoAcompanamiento, Derivacion, EstadoDerivacion, Estudiante,
    EvaluacionRiesgo, Intervencion,
)
from . import schemas


def estudiante_out(est: Estudiante) -> dict:
    return {
        "id": est.id, "usuario_id": est.usuario_id, "nombre": est.usuario.nombre,
        "documento": est.usuario.documento, "programa_id": est.programa_id,
        "programa": est.programa.nombre, "semestre": est.semestre,
        "promedio_acumulado": float(est.promedio_acumulado),
        "estado_matricula": est.estado_matricula,
        "tiene_apoyo_financiero": est.tiene_apoyo_financiero,
        "tiene_deuda_vigente": est.tiene_deuda_vigente,
    }


def ultima_evaluacion(db: Session, estudiante_id: int) -> EvaluacionRiesgo | None:
    return db.scalar(
        select(EvaluacionRiesgo)
        .where(EvaluacionRiesgo.estudiante_id == estudiante_id)
        .order_by(EvaluacionRiesgo.id.desc())
    )


def factor_principal(evaluacion: EvaluacionRiesgo | None) -> str | None:
    if not evaluacion or not evaluacion.detalle_factores:
        return None
    top = max(evaluacion.detalle_factores, key=lambda d: d["aporte"])
    return f"{top['nombre']}: {top['evidencia']}"


def caso_out(db: Session, caso: CasoAcompanamiento) -> dict:
    intervenciones = db.scalar(
        select(func.count(Intervencion.id)).where(Intervencion.caso_id == caso.id)) or 0
    abiertas = db.scalar(
        select(func.count(Derivacion.id))
        .where(Derivacion.caso_id == caso.id, Derivacion.estado == EstadoDerivacion.ABIERTA)) or 0
    ev = ultima_evaluacion(db, caso.estudiante_id)
    return {
        "id": caso.id, "estudiante_id": caso.estudiante_id,
        "estudiante": caso.estudiante.usuario.nombre,
        "programa": caso.estudiante.programa.nombre,
        "programa_id": caso.estudiante.programa_id,
        "consejero_id": caso.consejero_id,
        "consejero": caso.consejero.nombre if caso.consejero else None,
        "estado": caso.estado, "nivel_apertura": caso.nivel_apertura,
        "escalado": caso.escalado, "resultado": caso.resultado,
        "indice_actual": float(ev.indice) if ev else None,
        "indice_cierre": float(caso.indice_cierre) if caso.indice_cierre is not None else None,
        "fecha_apertura": caso.fecha_apertura, "fecha_cierre": caso.fecha_cierre,
        "intervenciones": intervenciones, "derivaciones_abiertas": abiertas,
    }


def caso_detalle_out(db: Session, caso: CasoAcompanamiento) -> dict:
    base = caso_out(db, caso)
    base["historial"] = [
        {"id": h.id, "estado_anterior": h.estado_anterior, "estado_nuevo": h.estado_nuevo,
         "motivo": h.motivo, "usuario": h.usuario.nombre if h.usuario else "Sistema",
         "fecha": h.fecha}
        for h in caso.historial
    ]
    base["evaluacion"] = ultima_evaluacion(db, caso.estudiante_id)
    # Las acciones que se ejecutaron sobre el caso, con quién las hizo (RQNF-03).
    from .services.auditoria import acciones_sobre
    base["acciones"] = [
        {"id": a.id, "usuario": a.usuario.nombre if a.usuario else "Sistema",
         "accion": a.accion, "detalle": a.detalle, "fecha": a.fecha}
        for a in acciones_sobre(db, "CASO", caso.id)
    ]
    return base


def intervencion_out(i: Intervencion) -> dict:
    return {
        "id": i.id, "caso_id": i.caso_id, "consejero": i.consejero.nombre, "tipo": i.tipo,
        "descripcion": i.descripcion, "compromisos": i.compromisos,
        "fecha_cita": i.fecha_cita, "asistio": i.asistio, "fecha": i.fecha,
    }


def derivacion_out(d: Derivacion) -> dict:
    return {
        "id": d.id, "caso_id": d.caso_id,
        "estudiante": d.caso.estudiante.usuario.nombre,
        "tipo_apoyo": d.tipo_apoyo, "estado": d.estado,
        "solicitante": d.solicitante.nombre, "observacion": d.observacion, "fecha": d.fecha,
    }
