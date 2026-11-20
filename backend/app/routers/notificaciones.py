"""Bandeja de notificaciones (RQF-14)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notificacion, Usuario
from ..schemas import NotificacionOut
from ..security import usuario_actual

router = APIRouter(prefix="/api/notificaciones", tags=["Notificaciones"])


@router.get("", response_model=list[NotificacionOut], summary="Mis notificaciones")
def listar(solo_pendientes: bool = False, db: Session = Depends(get_db),
           usuario: Usuario = Depends(usuario_actual)):
    q = select(Notificacion).where(Notificacion.usuario_id == usuario.id)
    if solo_pendientes:
        q = q.where(Notificacion.atendida.is_(False))
    return list(db.scalars(q.order_by(Notificacion.id.desc()).limit(100)))


@router.get("/pendientes", summary="Cuántas notificaciones sin atender tengo")
def pendientes(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_actual)):
    total = db.scalar(select(func.count(Notificacion.id)).where(
        Notificacion.usuario_id == usuario.id, Notificacion.atendida.is_(False))) or 0
    return {"pendientes": total}


@router.post("/{notificacion_id}/leer", response_model=NotificacionOut,
             summary="Marcar como leída")
def leer(notificacion_id: int, db: Session = Depends(get_db),
         usuario: Usuario = Depends(usuario_actual)):
    return _actualizar(db, notificacion_id, usuario, leida=True)


@router.post("/{notificacion_id}/atender", response_model=NotificacionOut,
             summary="Marcar como atendida")
def atender(notificacion_id: int, db: Session = Depends(get_db),
            usuario: Usuario = Depends(usuario_actual)):
    return _actualizar(db, notificacion_id, usuario, leida=True, atendida=True)


def _actualizar(db: Session, notificacion_id: int, usuario: Usuario, **campos) -> Notificacion:
    notificacion = db.get(Notificacion, notificacion_id)
    if notificacion is None or notificacion.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La notificación no existe")
    for campo, valor in campos.items():
        setattr(notificacion, campo, valor)
    db.commit()
    db.refresh(notificacion)
    return notificacion
