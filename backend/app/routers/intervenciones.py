"""Intervenciones y citas (RQF-09, RQF-10)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AccionAuditoria, EstadoCaso, Intervencion, RolNombre, Usuario,
)
from ..schemas import IntervencionCrear, IntervencionOut, RegistrarAsistencia
from ..security import exige_rol
from ..services import casos as servicio_casos
from ..services.auditoria import registrar as auditar
from ..services.notificaciones import notificar
from ..serializers import intervencion_out
from .casos import exige_acceso, obtener_caso

router = APIRouter(prefix="/api", tags=["Intervenciones"])
equipo = exige_rol(RolNombre.CONSEJERO, RolNombre.COORDINADOR, RolNombre.ADMINISTRADOR)


@router.get("/casos/{caso_id}/intervenciones", response_model=list[IntervencionOut],
            summary="Intervenciones de un caso")
def listar(caso_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(equipo)):
    """RQNF-03: el acceso queda registrado en la bitácora."""
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    intervenciones = list(db.scalars(
        select(Intervencion).where(Intervencion.caso_id == caso_id).order_by(Intervencion.id)))
    for i in intervenciones:
        auditar(db, usuario, "INTERVENCION", i.id, AccionAuditoria.LECTURA)
    db.commit()
    return [intervencion_out(i) for i in intervenciones]


@router.post("/casos/{caso_id}/intervenciones", response_model=IntervencionOut,
             status_code=status.HTTP_201_CREATED, summary="Registrar una intervención")
def crear(caso_id: int, datos: IntervencionCrear, db: Session = Depends(get_db),
          usuario: Usuario = Depends(equipo)):
    """RQF-09. Solo el consejero asignado; la primera pasa el caso a En seguimiento."""
    caso = obtener_caso(db, caso_id)
    if caso.estado == EstadoCaso.CERRADO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "El caso está cerrado: no admite nuevas intervenciones")
    if usuario.rol.nombre == RolNombre.CONSEJERO and caso.consejero_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Solo el consejero asignado puede registrar intervenciones")
    if caso.consejero_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "El caso todavía no tiene consejero asignado")
    if datos.fecha_cita and datos.fecha_cita < datetime.now():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "La cita no puede agendarse en una fecha pasada")

    primera = not servicio_casos.tiene_intervenciones(db, caso.id)
    intervencion = Intervencion(
        caso_id=caso.id, consejero_id=caso.consejero_id, tipo=datos.tipo,
        descripcion=datos.descripcion, compromisos=datos.compromisos,
        fecha_cita=datos.fecha_cita,
    )
    db.add(intervencion)
    db.flush()
    auditar(db, usuario, "INTERVENCION", intervencion.id, AccionAuditoria.ESCRITURA)

    if primera and caso.estado == EstadoCaso.ASIGNADO:
        servicio_casos.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO,
                                      usuario=usuario, motivo="PRIMERA_INTERVENCION")
    if datos.fecha_cita:                                    # RQF-10
        notificar(db, caso.estudiante.usuario_id, "CITA_PROXIMA",
                  f"Tienes una cita de acompañamiento el "
                  f"{datos.fecha_cita.strftime('%d/%m/%Y a las %H:%M')}", caso.id)
    db.commit()
    db.refresh(intervencion)
    return intervencion_out(intervencion)


@router.post("/intervenciones/{intervencion_id}/asistencia", response_model=IntervencionOut,
             summary="Registrar si el estudiante asistió a la cita")
def asistencia(intervencion_id: int, datos: RegistrarAsistencia, db: Session = Depends(get_db),
               usuario: Usuario = Depends(equipo)):
    intervencion = db.get(Intervencion, intervencion_id)
    if intervencion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La intervención no existe")
    if intervencion.fecha_cita is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Esa intervención no tiene una cita agendada")
    exige_acceso(db, intervencion.caso, usuario)
    intervencion.asistio = datos.asistio
    auditar(db, usuario, "INTERVENCION", intervencion.id, AccionAuditoria.ESCRITURA)
    db.commit()
    db.refresh(intervencion)
    return intervencion_out(intervencion)


@router.get("/citas", response_model=list[IntervencionOut], summary="Próximas citas del consejero")
def citas(db: Session = Depends(get_db), usuario: Usuario = Depends(equipo)):
    q = select(Intervencion).where(Intervencion.fecha_cita.is_not(None))
    if usuario.rol.nombre == RolNombre.CONSEJERO:
        q = q.where(Intervencion.consejero_id == usuario.id)
    return [intervencion_out(i) for i in db.scalars(q.order_by(Intervencion.fecha_cita))]
