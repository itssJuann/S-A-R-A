"""Servicio de notificaciones (RQF-14).

El envío por correo queda detrás de una función aparte para que en desarrollo
solo se registre en la bandeja interna y en producción se conecte un SMTP real.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..models import Notificacion, Usuario

log = logging.getLogger("sara.notificaciones")


def notificar(db: Session, usuario_id: int | None, tipo: str, mensaje: str,
              caso_id: int | None = None) -> Notificacion | None:
    if usuario_id is None:
        return None
    notificacion = Notificacion(usuario_id=usuario_id, tipo=tipo, mensaje=mensaje, caso_id=caso_id)
    db.add(notificacion)
    db.flush()
    _enviar_correo(db, usuario_id, tipo, mensaje)
    return notificacion


def _enviar_correo(db: Session, usuario_id: int, tipo: str, mensaje: str) -> None:
    """Punto de extensión: aquí se conecta el servidor SMTP institucional."""
    usuario = db.get(Usuario, usuario_id)
    if usuario:
        log.info("correo -> %s | %s | %s", usuario.correo, tipo, mensaje)
