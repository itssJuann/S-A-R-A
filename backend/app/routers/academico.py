"""Registro académico: estudiantes y matrículas (RQF-01)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Estudiante, Matricula, Rol, RolNombre, Usuario
from ..schemas import (
    EstudianteActualizar, EstudianteCrear, EstudianteOut, MatriculaCrear, MatriculaOut,
)
from ..security import exige_rol, hash_password, usuario_actual
from ..serializers import estudiante_out

router = APIRouter(prefix="/api", tags=["Registro académico"])
solo_admin = exige_rol(RolNombre.ADMINISTRADOR)
staff = exige_rol(RolNombre.ADMINISTRADOR, RolNombre.COORDINADOR,
                  RolNombre.CONSEJERO, RolNombre.DOCENTE, RolNombre.BIENESTAR)


@router.get("/estudiantes", response_model=list[EstudianteOut], summary="Listar estudiantes")
def listar(programa_id: int | None = None, buscar: str | None = None,
           db: Session = Depends(get_db), _: Usuario = Depends(staff)):
    q = select(Estudiante).join(Estudiante.usuario)
    if programa_id:
        q = q.where(Estudiante.programa_id == programa_id)
    if buscar:
        patron = f"%{buscar}%"
        q = q.where(Usuario.nombre.ilike(patron) | Usuario.documento.ilike(patron))
    return [estudiante_out(e) for e in db.scalars(q.order_by(Usuario.nombre))]


@router.post("/estudiantes", response_model=EstudianteOut, status_code=status.HTTP_201_CREATED,
             summary="Registrar estudiante")
def crear(datos: EstudianteCrear, db: Session = Depends(get_db),
          _: Usuario = Depends(solo_admin)):
    """RQF-01. Crea el usuario con rol ESTUDIANTE y su ficha académica."""
    rol = db.scalar(select(Rol).where(Rol.nombre == RolNombre.ESTUDIANTE))
    usuario = Usuario(
        documento=datos.documento, nombre=datos.nombre, correo=datos.correo,
        password_hash=hash_password(datos.password), rol_id=rol.id,
        programa_id=datos.programa_id,
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Ya existe un usuario con ese documento o correo")
    estudiante = Estudiante(
        usuario_id=usuario.id, programa_id=datos.programa_id, semestre=datos.semestre,
        promedio_acumulado=datos.promedio_acumulado, estado_matricula=datos.estado_matricula,
        tiene_apoyo_financiero=datos.tiene_apoyo_financiero,
        tiene_deuda_vigente=datos.tiene_deuda_vigente,
    )
    db.add(estudiante)
    db.commit()
    db.refresh(estudiante)
    return estudiante_out(estudiante)


@router.get("/estudiantes/{estudiante_id}", response_model=EstudianteOut, summary="Ver estudiante")
def ver(estudiante_id: int, db: Session = Depends(get_db), _: Usuario = Depends(staff)):
    return estudiante_out(_buscar(db, estudiante_id))


@router.patch("/estudiantes/{estudiante_id}", response_model=EstudianteOut,
              summary="Actualizar estudiante")
def actualizar(estudiante_id: int, datos: EstudianteActualizar, db: Session = Depends(get_db),
               _: Usuario = Depends(solo_admin)):
    estudiante = _buscar(db, estudiante_id)
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(estudiante, campo, valor)
    db.commit()
    db.refresh(estudiante)
    return estudiante_out(estudiante)


@router.post("/matriculas", response_model=MatriculaOut, status_code=status.HTTP_201_CREATED,
             summary="Matricular en una asignatura")
def matricular(datos: MatriculaCrear, db: Session = Depends(get_db),
               _: Usuario = Depends(solo_admin)):
    matricula = Matricula(**datos.model_dump())
    db.add(matricula)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "El estudiante ya está matriculado en esa asignatura en ese periodo")
    db.refresh(matricula)
    return matricula


@router.get("/matriculas", response_model=list[MatriculaOut], summary="Listar matrículas")
def listar_matriculas(estudiante_id: int | None = None, docente_id: int | None = None,
                      periodo: str | None = None, db: Session = Depends(get_db),
                      _: Usuario = Depends(staff)):
    q = select(Matricula)
    if estudiante_id:
        q = q.where(Matricula.estudiante_id == estudiante_id)
    if docente_id:
        q = q.where(Matricula.docente_id == docente_id)
    if periodo:
        q = q.where(Matricula.periodo == periodo)
    return list(db.scalars(q.order_by(Matricula.id)))


def _buscar(db: Session, estudiante_id: int) -> Estudiante:
    estudiante = db.get(Estudiante, estudiante_id)
    if estudiante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El estudiante no existe")
    return estudiante
