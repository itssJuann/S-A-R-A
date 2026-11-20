"""Captura de desempeño: notas e inasistencias (RQF-03, RQF-04).

Cada registro dispara el recálculo del índice de riesgo (RN-07) y, si
corresponde, la apertura del caso (RN-03).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import CORTE_VIGENTE, CORTES_POR_SEMESTRE, PERIODO_VIGENTE
from ..database import get_db
from ..models import Estudiante, Inasistencia, Matricula, Nota, RolNombre, Usuario
from ..schemas import (
    BoletinOut, FilaCurso, InasistenciaCrear, InasistenciaOut, NotaCrear, NotaOut,
    ResultadoRegistro,
)
from ..security import exige_rol, usuario_actual
from ..services.boletin import boletin_de
from ..services.riesgo import ErrorModelo, evaluar_y_atender
from ..serializers import ultima_evaluacion

router = APIRouter(prefix="/api/desempeno", tags=["Captura de desempeño"])
docente_o_admin = exige_rol(RolNombre.DOCENTE, RolNombre.ADMINISTRADOR)


def _matricula_del_docente(db: Session, matricula_id: int, usuario: Usuario) -> Matricula:
    matricula = db.get(Matricula, matricula_id)
    if matricula is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La matrícula no existe")
    if usuario.rol.nombre == RolNombre.DOCENTE and matricula.docente_id != usuario.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "No puedes registrar desempeño de una asignatura que no dictas")
    return matricula


@router.post("/notas", response_model=ResultadoRegistro, status_code=status.HTTP_201_CREATED,
             summary="Registrar la nota de un corte")
def registrar_nota(datos: NotaCrear, db: Session = Depends(get_db),
                   usuario: Usuario = Depends(docente_o_admin)):
    """RQF-03. Al guardar, se recalcula el índice del estudiante."""
    matricula = _matricula_del_docente(db, datos.matricula_id, usuario)
    existente = db.scalar(select(Nota).where(
        Nota.matricula_id == matricula.id, Nota.corte == datos.corte))
    if existente:
        existente.valor = datos.valor
        existente.registrada_por = usuario.id
    else:
        db.add(Nota(matricula_id=matricula.id, corte=datos.corte, valor=datos.valor,
                    registrada_por=usuario.id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "No se pudo guardar la nota")
    return _evaluar(db, matricula, "Nota registrada")


@router.post("/inasistencias", response_model=ResultadoRegistro,
             status_code=status.HTTP_201_CREATED, summary="Registrar una inasistencia")
def registrar_inasistencia(datos: InasistenciaCrear, db: Session = Depends(get_db),
                           usuario: Usuario = Depends(docente_o_admin)):
    """RQF-04. No se admiten fechas futuras."""
    if datos.fecha_sesion > date.today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "No se pueden registrar inasistencias de fechas futuras")
    matricula = _matricula_del_docente(db, datos.matricula_id, usuario)
    db.add(Inasistencia(matricula_id=matricula.id, fecha_sesion=datos.fecha_sesion,
                        justificada=datos.justificada, registrada_por=usuario.id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Esa inasistencia ya estaba registrada para esa sesión")
    return _evaluar(db, matricula, "Inasistencia registrada")


@router.get("/cursos/{matricula_periodo}", response_model=list[FilaCurso],
            summary="Listado de un curso para el docente")
def curso(matricula_periodo: str, asignatura_id: int, corte: int = CORTE_VIGENTE,
          db: Session = Depends(get_db), usuario: Usuario = Depends(docente_o_admin)):
    """Las filas de la pantalla de captura: nota, inasistencias y riesgo estimado."""
    q = select(Matricula).where(Matricula.periodo == matricula_periodo,
                                Matricula.asignatura_id == asignatura_id)
    if usuario.rol.nombre == RolNombre.DOCENTE:
        q = q.where(Matricula.docente_id == usuario.id)
    filas = []
    for m in db.scalars(q):
        nota = db.scalar(select(Nota).where(Nota.matricula_id == m.id, Nota.corte == corte))
        faltas = db.scalar(select(func.count(Inasistencia.id)).where(
            Inasistencia.matricula_id == m.id, Inasistencia.justificada.is_(False))) or 0
        ev = ultima_evaluacion(db, m.estudiante_id)
        filas.append({
            "matricula_id": m.id, "estudiante_id": m.estudiante_id,
            "estudiante": m.estudiante.usuario.nombre,
            "documento": m.estudiante.usuario.documento,
            "semestre": m.estudiante.semestre,
            "nota": float(nota.valor) if nota else None,
            "inasistencias": faltas, "sesiones": m.sesiones_programadas,
            "nivel": ev.nivel if ev else None,
            "indice": float(ev.indice) if ev else None,
        })
    filas.sort(key=lambda f: f["estudiante"])
    return filas


@router.get("/notas", response_model=list[NotaOut], summary="Notas de una matrícula")
def listar_notas(matricula_id: int, db: Session = Depends(get_db),
                 usuario: Usuario = Depends(usuario_actual)):
    return list(db.scalars(select(Nota).where(Nota.matricula_id == matricula_id)
                           .order_by(Nota.corte)))


@router.get("/inasistencias", response_model=list[InasistenciaOut],
            summary="Inasistencias de una matrícula")
def listar_inasistencias(matricula_id: int, db: Session = Depends(get_db),
                         usuario: Usuario = Depends(usuario_actual)):
    return list(db.scalars(select(Inasistencia)
                           .where(Inasistencia.matricula_id == matricula_id)
                           .order_by(Inasistencia.fecha_sesion)))


def _evaluar(db: Session, matricula: Matricula, mensaje: str) -> dict:
    try:
        resultado = evaluar_y_atender(db, matricula.estudiante, periodo=matricula.periodo)
    except ErrorModelo as e:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    evaluacion = resultado["evaluacion"]
    caso = resultado["caso"]
    return {
        "mensaje": mensaje, "indice": float(evaluacion.indice), "nivel": evaluacion.nivel,
        "alerta_generada": resultado["alerta"],
        "caso_id": caso.id if caso else None, "caso_nuevo": resultado["caso_nuevo"],
    }


@router.get("/boletin/{estudiante_id}", response_model=BoletinOut,
            summary="Notas de un estudiante corte por corte")
def boletin(estudiante_id: int, periodo: str = PERIODO_VIGENTE,
            db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_actual)):
    """El estudiante solo puede consultar el suyo; el resto de roles, el de cualquiera."""
    estudiante = db.get(Estudiante, estudiante_id)
    if estudiante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El estudiante no existe")
    if (usuario.rol.nombre == RolNombre.ESTUDIANTE
            and estudiante.usuario_id != usuario.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Solo puedes consultar tu propio boletín")
    return boletin_de(db, estudiante, periodo=periodo)
