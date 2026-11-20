"""Casos de acompañamiento (RQF-07, RQF-08, RQF-12, RQF-13)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..alcance import filtrar_casos, puede_ver_caso, puede_ver_estudiante
from ..database import get_db
from ..models import (
    AccionAuditoria, CasoAcompanamiento, Estudiante, EstadoCaso, NivelRiesgo, RolNombre,
    Usuario,
)
from ..schemas import (
    AbrirCaso, CambiarEstado, CasoDetalleOut, CasoOut, CerrarCaso, ReabrirCaso, Reasignar,
)
from ..security import exige_rol, usuario_actual
from ..services import casos as servicio
from ..services.auditoria import registrar as auditar
from ..services.escalamiento import revisar_casos_criticos
from ..serializers import caso_detalle_out, caso_out

router = APIRouter(prefix="/api/casos", tags=["Casos de acompañamiento"])
equipo = exige_rol(RolNombre.CONSEJERO, RolNombre.COORDINADOR,
                   RolNombre.BIENESTAR, RolNombre.ADMINISTRADOR)
coord_o_admin = exige_rol(RolNombre.COORDINADOR, RolNombre.ADMINISTRADOR)


TEXTO_ESTADO = {
    EstadoCaso.ABIERTO: "Abierto", EstadoCaso.ASIGNADO: "Asignado",
    EstadoCaso.EN_SEGUIMIENTO: "En seguimiento", EstadoCaso.EN_EVALUACION: "En evaluación",
    EstadoCaso.CERRADO: "Cerrado",
}


def _legible(estado: EstadoCaso) -> str:
    return TEXTO_ESTADO.get(estado, estado.value)


def obtener_caso(db: Session, caso_id: int) -> CasoAcompanamiento:
    caso = db.get(CasoAcompanamiento, caso_id)
    if caso is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El caso no existe")
    return caso


def exige_acceso(db: Session, caso: CasoAcompanamiento, usuario: Usuario) -> None:
    """RN-10. El alcance de cada rol está definido en app/alcance.py."""
    if not puede_ver_caso(db, usuario, caso):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Este caso está fuera de tu alcance")


@router.get("", response_model=list[CasoOut], summary="Listar casos")
def listar(estado: EstadoCaso | None = None, nivel: NivelRiesgo | None = None,
           escalados: bool = False, mios: bool = False, programa_id: int | None = None,
           db: Session = Depends(get_db), usuario: Usuario = Depends(equipo)):
    q = filtrar_casos(db, usuario, select(CasoAcompanamiento))
    if estado:
        q = q.where(CasoAcompanamiento.estado == estado)
    if nivel:
        q = q.where(CasoAcompanamiento.nivel_apertura == nivel)
    if escalados:
        q = q.where(CasoAcompanamiento.escalado.is_(True))
    if mios:
        q = q.where(CasoAcompanamiento.consejero_id == usuario.id)
    casos = list(db.scalars(q.order_by(CasoAcompanamiento.id.desc())))
    if programa_id:
        casos = [c for c in casos if c.estudiante.programa_id == programa_id]
    return [caso_out(db, c) for c in casos]


@router.post("", response_model=CasoDetalleOut, status_code=status.HTTP_201_CREATED,
             summary="Abrir un caso manualmente")
def abrir(datos: AbrirCaso, db: Session = Depends(get_db),
          usuario: Usuario = Depends(coord_o_admin)):
    """RQF-08. El coordinador abre un caso que el índice no disparó."""
    estudiante = db.get(Estudiante, datos.estudiante_id)
    if estudiante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El estudiante no existe")
    if not puede_ver_estudiante(db, usuario, estudiante.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Este estudiante no pertenece a tu programa")
    consejero = None
    if datos.consejero_id:
        consejero = db.get(Usuario, datos.consejero_id)
        if consejero is None or consejero.rol.nombre != RolNombre.CONSEJERO:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "El consejero no existe")
    try:
        caso = servicio.abrir_manualmente(db, estudiante, usuario, datos.motivo, consejero)
    except servicio.ErrorCaso as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    auditar(db, usuario, "CASO", caso.id, AccionAuditoria.APERTURA,
            f"Apertura manual: {datos.motivo.strip()}")
    db.commit()
    return caso_detalle_out(db, caso)


@router.get("/tablero", summary="Casos agrupados por estado (tablero)")
def tablero(db: Session = Depends(get_db), usuario: Usuario = Depends(equipo)):
    q = filtrar_casos(db, usuario, select(CasoAcompanamiento))
    columnas = {estado.value: [] for estado in EstadoCaso}
    for caso in db.scalars(q.order_by(CasoAcompanamiento.id.desc())):
        columnas[caso.estado.value].append(caso_out(db, caso))
    return columnas


@router.get("/{caso_id}", response_model=CasoDetalleOut, summary="Detalle de un caso")
def detalle(caso_id: int, db: Session = Depends(get_db), usuario: Usuario = Depends(equipo)):
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    auditar(db, usuario, "CASO", caso.id, AccionAuditoria.LECTURA)
    db.commit()
    return caso_detalle_out(db, caso)


@router.post("/{caso_id}/estado", response_model=CasoDetalleOut, summary="Cambiar el estado")
def cambiar_estado(caso_id: int, datos: CambiarEstado, db: Session = Depends(get_db),
                   usuario: Usuario = Depends(equipo)):
    """RQF-12. El sistema rechaza cualquier transición que salte un estado."""
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    if datos.estado == EstadoCaso.CERRADO:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Para cerrar un caso usa /casos/{id}/cerrar: exige un resultado")
    try:
        anterior = caso.estado
        servicio.cambiar_estado(db, caso, datos.estado, usuario=usuario, motivo=datos.motivo)
    except servicio.ErrorCaso as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    auditar(db, usuario, "CASO", caso.id, AccionAuditoria.CAMBIO_ESTADO,
            f"{_legible(anterior)} → {_legible(datos.estado)}")
    db.commit()
    return caso_detalle_out(db, caso)


@router.post("/{caso_id}/cerrar", response_model=CasoDetalleOut, summary="Cerrar el caso")
def cerrar(caso_id: int, datos: CerrarCaso, db: Session = Depends(get_db),
           usuario: Usuario = Depends(equipo)):
    """RN-08: exige resultado, recalcula el índice y verifica las derivaciones."""
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    try:
        servicio.cerrar(db, caso, datos.resultado, usuario)
    except servicio.ErrorCaso as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    auditar(db, usuario, "CASO", caso.id, AccionAuditoria.CIERRE,
            f"Cierre con resultado {datos.resultado.value}")
    db.commit()
    return caso_detalle_out(db, caso)


@router.post("/{caso_id}/reasignar", response_model=CasoDetalleOut, summary="Reasignar consejero")
def reasignar(caso_id: int, datos: Reasignar, db: Session = Depends(get_db),
              usuario: Usuario = Depends(coord_o_admin)):
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    consejero = db.get(Usuario, datos.consejero_id)
    if consejero is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El consejero no existe")
    try:
        servicio.reasignar(db, caso, consejero, usuario)
    except servicio.ErrorCaso as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    auditar(db, usuario, "CASO", caso.id, AccionAuditoria.REASIGNACION,
            f"Reasignado a {consejero.nombre}")
    db.commit()
    return caso_detalle_out(db, caso)


@router.post("/{caso_id}/reabrir", response_model=CasoDetalleOut,
             summary="Reabrir un caso cerrado")
def reabrir(caso_id: int, datos: ReabrirCaso, db: Session = Depends(get_db),
            usuario: Usuario = Depends(coord_o_admin)):
    """Acción de supervisión: devuelve a seguimiento un caso que se cerró antes de tiempo."""
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    try:
        servicio.reabrir(db, caso, usuario, datos.motivo)
    except servicio.ErrorCaso as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    auditar(db, usuario, "CASO", caso.id, AccionAuditoria.REAPERTURA,
            f"Reapertura: {datos.motivo.strip()}")
    db.commit()
    return caso_detalle_out(db, caso)


@router.post("/{caso_id}/atender-escalamiento", response_model=CasoDetalleOut,
             summary="Tomar un caso escalado")
def atender_escalamiento(caso_id: int, db: Session = Depends(get_db),
                         usuario: Usuario = Depends(coord_o_admin)):
    caso = obtener_caso(db, caso_id)
    exige_acceso(db, caso, usuario)
    try:
        servicio.atender_escalamiento(db, caso, usuario)
    except servicio.ErrorCaso as e:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    auditar(db, usuario, "CASO", caso.id, AccionAuditoria.ESCALAMIENTO,
            "El coordinador tomó el escalamiento")
    db.commit()
    return caso_detalle_out(db, caso)


@router.post("/revisar-escalamientos", summary="Ejecutar la revisión de casos críticos")
def revisar(db: Session = Depends(get_db), _: Usuario = Depends(coord_o_admin)):
    """RQF-13. En producción lo ejecuta el planificador todos los días."""
    return revisar_casos_criticos(db)
