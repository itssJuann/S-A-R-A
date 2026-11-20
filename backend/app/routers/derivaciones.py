"""Derivaciones a bienestar universitario (RQF-11)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    AccionAuditoria, Derivacion, EstadoCaso, EstadoDerivacion, RolNombre, Usuario,
)
from ..schemas import AtenderDerivacion, DerivacionCrear, DerivacionOut
from ..security import exige_rol
from ..services.auditoria import registrar as auditar
from ..services.notificaciones import notificar
from ..serializers import derivacion_out
from .casos import exige_acceso, obtener_caso

router = APIRouter(prefix="/api", tags=["Derivaciones"])
consejeria = exige_rol(RolNombre.CONSEJERO, RolNombre.COORDINADOR, RolNombre.ADMINISTRADOR)
bienestar = exige_rol(RolNombre.BIENESTAR, RolNombre.ADMINISTRADOR)
todos = exige_rol(RolNombre.CONSEJERO, RolNombre.COORDINADOR,
                  RolNombre.BIENESTAR, RolNombre.ADMINISTRADOR)


@router.post("/casos/{caso_id}/derivaciones", response_model=DerivacionOut,
             status_code=status.HTTP_201_CREATED, summary="Derivar un caso a bienestar")
def crear(caso_id: int, datos: DerivacionCrear, db: Session = Depends(get_db),
          usuario: Usuario = Depends(consejeria)):
    """RQF-11. El caso no podrá cerrarse mientras la derivación siga abierta."""
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    if caso.estado == EstadoCaso.CERRADO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "El caso está cerrado: no admite nuevas derivaciones")
    repetida = db.scalar(select(Derivacion).where(
        Derivacion.caso_id == caso.id, Derivacion.tipo_apoyo == datos.tipo_apoyo,
        Derivacion.estado == EstadoDerivacion.ABIERTA))
    if repetida:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Ya hay una derivación abierta de tipo {datos.tipo_apoyo.value}")

    derivacion = Derivacion(caso_id=caso.id, tipo_apoyo=datos.tipo_apoyo,
                            solicitada_por=usuario.id, observacion=datos.observacion)
    db.add(derivacion)
    db.flush()
    auditar(db, usuario, "DERIVACION", derivacion.id, AccionAuditoria.ESCRITURA)
    for u in db.scalars(select(Usuario).where(Usuario.rol.has(nombre=RolNombre.BIENESTAR))):
        notificar(db, u.id, "DERIVACION",
                  f"Nueva derivación de apoyo {datos.tipo_apoyo.value} en el caso #{caso.id}",
                  caso.id)
    db.commit()
    db.refresh(derivacion)
    return derivacion_out(derivacion)


@router.get("/derivaciones", response_model=list[DerivacionOut], summary="Listar derivaciones")
def listar(estado: EstadoDerivacion | None = None, db: Session = Depends(get_db),
           usuario: Usuario = Depends(todos)):
    q = select(Derivacion)
    if estado:
        q = q.where(Derivacion.estado == estado)
    derivaciones = list(db.scalars(q.order_by(Derivacion.id.desc())))
    if usuario.rol.nombre == RolNombre.CONSEJERO:
        derivaciones = [d for d in derivaciones if d.caso.consejero_id == usuario.id]
    for d in derivaciones:
        auditar(db, usuario, "DERIVACION", d.id, AccionAuditoria.LECTURA)
    db.commit()
    return [derivacion_out(d) for d in derivaciones]


@router.post("/derivaciones/{derivacion_id}/atender", response_model=DerivacionOut,
             summary="Bienestar atiende o rechaza la derivación")
def atender(derivacion_id: int, datos: AtenderDerivacion, db: Session = Depends(get_db),
            usuario: Usuario = Depends(bienestar)):
    derivacion = db.get(Derivacion, derivacion_id)
    if derivacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La derivación no existe")
    if derivacion.estado != EstadoDerivacion.ABIERTA:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"La derivación ya está {derivacion.estado.value}")
    if datos.estado == EstadoDerivacion.ABIERTA:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Indica si la derivación fue ATENDIDA o RECHAZADA")
    derivacion.estado = datos.estado
    derivacion.atendida_por = usuario.id
    if datos.observacion:
        derivacion.observacion = datos.observacion
    auditar(db, usuario, "DERIVACION", derivacion.id, AccionAuditoria.ESCRITURA)
    notificar(db, derivacion.caso.consejero_id, "DERIVACION",
              f"La derivación #{derivacion.id} quedó {datos.estado.value}", derivacion.caso_id)
    db.commit()
    db.refresh(derivacion)
    return derivacion_out(derivacion)
