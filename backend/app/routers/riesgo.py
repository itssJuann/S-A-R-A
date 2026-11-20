"""Motor de riesgo expuesto como API (RQF-05, RQF-06)."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import CORTE_VIGENTE, CORTES_POR_SEMESTRE, PERIODO_VIGENTE
from ..alcance import estudiantes_de, puede_ver_estudiante
from ..database import get_db
from ..models import Estudiante, EvaluacionRiesgo, NivelRiesgo, RolNombre, Usuario
from ..schemas import (
    EstudianteRiesgoOut, EvaluacionOut, ResumenReevaluacion,
)
from ..security import exige_rol
from ..services import casos as servicio_casos
from ..services.riesgo import (
    ErrorModelo, calcular_indice, evaluar_y_atender, reevaluar_poblacion,
)
from ..serializers import estudiante_out, factor_principal, ultima_evaluacion

router = APIRouter(prefix="/api/riesgo", tags=["Motor de riesgo"])
# Solo quien decide sobre el riesgo entra aquí. El docente ve el nivel de sus
# estudiantes dentro de la pantalla de captura; bienestar trabaja desde las
# derivaciones que le llegan, no desde el listado de la población.
staff = exige_rol(RolNombre.ADMINISTRADOR, RolNombre.COORDINADOR, RolNombre.CONSEJERO)
coord_o_admin = exige_rol(RolNombre.ADMINISTRADOR, RolNombre.COORDINADOR)


@router.get("/estudiantes", response_model=list[EstudianteRiesgoOut],
            summary="Estudiantes con su índice y nivel de riesgo")
def listado(nivel: NivelRiesgo | None = None, programa_id: int | None = None,
            sin_caso: bool = False, buscar: str | None = None,
            db: Session = Depends(get_db), usuario: Usuario = Depends(staff)):
    q = select(Estudiante).join(Estudiante.usuario)
    # Cada rol ve solo la parte de la población que le corresponde (RN-10).
    permitidos = estudiantes_de(db, usuario)
    if permitidos is not None:
        q = q.where(Estudiante.id.in_(permitidos))
    if programa_id:
        q = q.where(Estudiante.programa_id == programa_id)
    if buscar:
        patron = f"%{buscar}%"
        q = q.where(Usuario.nombre.ilike(patron) | Usuario.documento.ilike(patron))
    salida = []
    for est in db.scalars(q):
        ev = ultima_evaluacion(db, est.id)
        if nivel and (ev is None or ev.nivel != nivel):
            continue
        caso = servicio_casos.caso_abierto_de(db, est.id)
        if sin_caso and caso is not None:
            continue
        fila = estudiante_out(est)
        fila.update({
            "indice": float(ev.indice) if ev else None,
            "nivel": ev.nivel if ev else None,
            "factor_principal": factor_principal(ev),
            "caso_id": caso.id if caso else None,
            "caso_estado": caso.estado if caso else None,
        })
        salida.append(fila)
    salida.sort(key=lambda f: (-(f["indice"] or -1), f["nombre"]))
    return salida


@router.get("/estudiantes/{estudiante_id}/evaluaciones", response_model=list[EvaluacionOut],
            summary="Historial de evaluaciones de un estudiante")
def historial(estudiante_id: int, limite: int = Query(default=10, le=100),
              db: Session = Depends(get_db), usuario: Usuario = Depends(staff)):
    _exige_alcance(db, usuario, estudiante_id)
    return list(db.scalars(
        select(EvaluacionRiesgo).where(EvaluacionRiesgo.estudiante_id == estudiante_id)
        .order_by(EvaluacionRiesgo.id.desc()).limit(limite)))


@router.get("/estudiantes/{estudiante_id}/simular", summary="Simular el índice sin guardarlo")
def simular(estudiante_id: int, db: Session = Depends(get_db),
            usuario: Usuario = Depends(staff)):
    """Útil para explicarle al estudiante cómo se compone su índice."""
    _exige_alcance(db, usuario, estudiante_id)
    est = _buscar(db, estudiante_id)
    try:
        indice, nivel, detalle, version = calcular_indice(db, est)
    except ErrorModelo as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return {"estudiante_id": est.id, "indice": indice, "nivel": nivel,
            "version_modelo": version, "detalle_factores": [d.__dict__ for d in detalle]}


@router.post("/estudiantes/{estudiante_id}/evaluar", response_model=EvaluacionOut,
             summary="Forzar la evaluación de un estudiante")
def evaluar_uno(estudiante_id: int, db: Session = Depends(get_db),
                usuario: Usuario = Depends(coord_o_admin)):
    _exige_alcance(db, usuario, estudiante_id)
    est = _buscar(db, estudiante_id)
    try:
        return evaluar_y_atender(db, est)["evaluacion"]
    except ErrorModelo as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.post("/reevaluar", response_model=ResumenReevaluacion,
             summary="Recalcular el índice de toda la población (cierre de corte)")
def reevaluar(corte: int = Query(default=CORTE_VIGENTE, ge=1, le=CORTES_POR_SEMESTRE),
              periodo: str = PERIODO_VIGENTE,
              db: Session = Depends(get_db), _: Usuario = Depends(coord_o_admin)):
    """RN-07, RQNF-02. En producción lo dispara el planificador al iniciar el corte."""
    try:
        return reevaluar_poblacion(db, periodo=periodo, corte=corte)
    except ErrorModelo as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


def _buscar(db: Session, estudiante_id: int) -> Estudiante:
    est = db.get(Estudiante, estudiante_id)
    if est is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El estudiante no existe")
    return est


def _exige_alcance(db: Session, usuario: Usuario, estudiante_id: int) -> None:
    if not puede_ver_estudiante(db, usuario, estudiante_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Este estudiante está fuera de tu alcance")
