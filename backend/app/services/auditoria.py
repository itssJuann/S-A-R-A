"""Bitácora de acceso a información sensible (RQNF-03)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AccionAuditoria, BitacoraAcceso, Usuario


def registrar(db: Session, usuario: Usuario, recurso: str, recurso_id: int,
              accion: AccionAuditoria = AccionAuditoria.LECTURA,
              detalle: str | None = None) -> None:
    """Deja constancia de una acción. `detalle` la describe en palabras."""
    db.add(BitacoraAcceso(
        usuario_id=usuario.id, recurso=recurso, recurso_id=recurso_id,
        accion=accion, detalle=detalle))
    db.flush()


def acciones_sobre(db: Session, recurso: str, recurso_id: int) -> list[BitacoraAcceso]:
    """Las acciones registradas sobre un recurso, de la más reciente a la más antigua."""
    return list(db.scalars(
        select(BitacoraAcceso)
        .where(BitacoraAcceso.recurso == recurso, BitacoraAcceso.recurso_id == recurso_id)
        .where(BitacoraAcceso.accion != AccionAuditoria.LECTURA)
        .order_by(BitacoraAcceso.id.desc())
    ))
