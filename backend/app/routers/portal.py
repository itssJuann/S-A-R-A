"""Portal del estudiante (RQF-15).

RQNF-03: el estudiante ve su nivel, sus citas y sus compromisos, pero nunca
las notas de intervención del consejero ni el desglose del cálculo del índice.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Estudiante, Intervencion, RolNombre, Usuario
from ..schemas import MiEstadoOut
from ..security import exige_rol
from ..services import casos as servicio_casos
from ..services.boletin import boletin_de
from ..serializers import ultima_evaluacion

router = APIRouter(prefix="/api/portal", tags=["Portal del estudiante"])
solo_estudiante = exige_rol(RolNombre.ESTUDIANTE)


@router.get("/mi-estado", response_model=MiEstadoOut, summary="Mi situación académica")
def mi_estado(db: Session = Depends(get_db), usuario: Usuario = Depends(solo_estudiante)):
    est = db.scalar(select(Estudiante).where(Estudiante.usuario_id == usuario.id))
    if est is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay ficha académica para este usuario")

    evaluacion = ultima_evaluacion(db, est.id)
    caso = servicio_casos.caso_abierto_de(db, est.id)
    salida = {
        "estudiante": usuario.nombre, "programa": est.programa.nombre,
        "semestre": est.semestre,
        "nivel": evaluacion.nivel if evaluacion else None,
        "caso_id": caso.id if caso else None,
        "caso_estado": caso.estado if caso else None,
        "consejero": caso.consejero.nombre if caso and caso.consejero else None,
        "proxima_cita": None, "compromisos": [],
        "boletin": boletin_de(db, est),
    }
    if caso is None:
        return salida

    intervenciones = list(db.scalars(
        select(Intervencion).where(Intervencion.caso_id == caso.id).order_by(Intervencion.id)))

    futuras = [i for i in intervenciones if i.fecha_cita and i.fecha_cita >= datetime.now()]
    if futuras:
        proxima = min(futuras, key=lambda i: i.fecha_cita)
        salida["proxima_cita"] = {
            "intervencion_id": proxima.id, "fecha_cita": proxima.fecha_cita,
            "consejero": proxima.consejero.nombre, "asistio": proxima.asistio,
        }
    # Solo los compromisos acordados, nunca la descripción de la intervención.
    salida["compromisos"] = [
        {"intervencion_id": i.id, "texto": i.compromisos, "fecha": i.fecha}
        for i in intervenciones if i.compromisos
    ]
    return salida
