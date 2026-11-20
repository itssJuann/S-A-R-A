"""Alcance de cada rol: qué parte de la información puede ver (RN-10, RQNF-03).

Un solo lugar decide qué ve cada rol, en vez de repetir la condición en cada
router. Las funciones devuelven `None` cuando el rol no tiene restricción
(el administrador) y un conjunto de identificadores cuando sí la tiene.

    ADMINISTRADOR  todo
    COORDINADOR    los programas que coordina
    CONSEJERO      solo los estudiantes de los casos que tiene asignados
    BIENESTAR      solo los casos con derivación a bienestar
    DOCENTE        solo las asignaturas que dicta
    ESTUDIANTE     solo su propia ficha
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import (
    CasoAcompanamiento, Derivacion, Estudiante, Matricula, Programa, RolNombre, Usuario,
)

# Roles cuyo alcance es "toda la institución".
SIN_RESTRICCION = {RolNombre.ADMINISTRADOR}


def programas_de(db: Session, usuario: Usuario) -> set[int] | None:
    """Programas que el usuario puede ver. `None` = todos."""
    rol = usuario.rol.nombre
    if rol in SIN_RESTRICCION:
        return None
    if rol == RolNombre.COORDINADOR:
        # Los que coordina formalmente, más el programa al que está adscrito.
        ids = set(db.scalars(
            select(Programa.id).where(Programa.coordinador_id == usuario.id)))
        if usuario.programa_id:
            ids.add(usuario.programa_id)
        return ids
    if rol in (RolNombre.CONSEJERO, RolNombre.DOCENTE):
        return {usuario.programa_id} if usuario.programa_id else set()
    return None if rol == RolNombre.BIENESTAR else set()


def estudiantes_de(db: Session, usuario: Usuario) -> set[int] | None:
    """Identificadores de estudiante que el usuario puede consultar. `None` = todos."""
    rol = usuario.rol.nombre
    if rol in SIN_RESTRICCION:
        return None

    if rol == RolNombre.COORDINADOR:
        programas = programas_de(db, usuario) or set()
        return set(db.scalars(
            select(Estudiante.id).where(Estudiante.programa_id.in_(programas))))

    if rol == RolNombre.CONSEJERO:
        # Solo a quienes acompaña: los estudiantes de sus casos.
        return set(db.scalars(
            select(CasoAcompanamiento.estudiante_id)
            .where(CasoAcompanamiento.consejero_id == usuario.id)))

    if rol == RolNombre.BIENESTAR:
        # Solo a quienes le derivaron.
        return set(db.scalars(
            select(CasoAcompanamiento.estudiante_id)
            .join(Derivacion, Derivacion.caso_id == CasoAcompanamiento.id)))

    if rol == RolNombre.DOCENTE:
        return set(db.scalars(
            select(Matricula.estudiante_id).where(Matricula.docente_id == usuario.id)))

    if rol == RolNombre.ESTUDIANTE:
        propio = db.scalar(select(Estudiante.id).where(Estudiante.usuario_id == usuario.id))
        return {propio} if propio else set()

    return set()


def puede_ver_estudiante(db: Session, usuario: Usuario, estudiante_id: int) -> bool:
    permitidos = estudiantes_de(db, usuario)
    return permitidos is None or estudiante_id in permitidos


def filtrar_casos(db: Session, usuario: Usuario, q):
    """Añade a una consulta de casos la condición que corresponde al rol."""
    rol = usuario.rol.nombre
    if rol in SIN_RESTRICCION:
        return q
    if rol == RolNombre.CONSEJERO:
        return q.where(CasoAcompanamiento.consejero_id == usuario.id)
    if rol == RolNombre.BIENESTAR:
        con_derivacion = select(Derivacion.caso_id)
        return q.where(CasoAcompanamiento.id.in_(con_derivacion))
    if rol == RolNombre.COORDINADOR:
        programas = programas_de(db, usuario) or set()
        suyos = select(Estudiante.id).where(Estudiante.programa_id.in_(programas))
        return q.where(CasoAcompanamiento.estudiante_id.in_(suyos))
    if rol == RolNombre.ESTUDIANTE:
        propio = select(Estudiante.id).where(Estudiante.usuario_id == usuario.id)
        return q.where(CasoAcompanamiento.estudiante_id.in_(propio))
    return q.where(False)


def puede_ver_caso(db: Session, usuario: Usuario, caso: CasoAcompanamiento) -> bool:
    rol = usuario.rol.nombre
    if rol in SIN_RESTRICCION:
        return True
    if rol == RolNombre.CONSEJERO:
        return caso.consejero_id == usuario.id
    if rol == RolNombre.BIENESTAR:
        return bool(db.scalar(
            select(Derivacion.id).where(Derivacion.caso_id == caso.id).limit(1)))
    if rol == RolNombre.COORDINADOR:
        return caso.estudiante.programa_id in (programas_de(db, usuario) or set())
    if rol == RolNombre.ESTUDIANTE:
        return caso.estudiante.usuario_id == usuario.id
    return False


def filtrar_usuarios(db: Session, usuario: Usuario, q):
    """El coordinador solo ve al personal de su programa."""
    if usuario.rol.nombre in SIN_RESTRICCION:
        return q
    programas = programas_de(db, usuario)
    if programas is None:
        return q
    return q.where(or_(Usuario.programa_id.in_(programas), Usuario.programa_id.is_(None)))


def estudiantes_para_indicadores(db: Session, usuario: Usuario) -> set[int] | None:
    """Alcance de los indicadores de retención (RQF-15).

    Bienestar es una oficina institucional: atiende solo las derivaciones que le
    llegan, pero sus indicadores son los de toda la universidad. El coordinador,
    en cambio, mide su propio programa.
    """
    if usuario.rol.nombre in SIN_RESTRICCION | {RolNombre.BIENESTAR}:
        return None
    return estudiantes_de(db, usuario)


def programas_para_indicadores(db: Session, usuario: Usuario) -> set[int] | None:
    if usuario.rol.nombre in SIN_RESTRICCION | {RolNombre.BIENESTAR}:
        return None
    return programas_de(db, usuario)
