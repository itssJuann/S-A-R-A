"""Administración: usuarios, programas, asignaturas, modelo de riesgo y auditoría.

Cubre RQF-02 y parte de RQNF-03.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..alcance import estudiantes_de, filtrar_usuarios, programas_de
from ..database import get_db
from ..models import (
    AccionAuditoria, Asignatura, CasoAcompanamiento, BitacoraAcceso, FactorRiesgo, Matricula, Programa, Rol, RolNombre, Usuario,
)
from ..schemas import (
    AsignaturaCrear, AsignaturaOut, BitacoraOut, ConfigurarModelo, FactorOut,
    ProgramaCrear, ProgramaOut, UsuarioCrear, UsuarioOut,
)
from ..security import exige_rol, hash_password, usuario_actual
from ..factores import CALCULADORES

router = APIRouter(prefix="/api/admin", tags=["Administración"])
solo_admin = exige_rol(RolNombre.ADMINISTRADOR)
admin_o_coord = exige_rol(RolNombre.ADMINISTRADOR, RolNombre.COORDINADOR)


# ----------------------------- Usuarios -----------------------------
@router.get("/usuarios", response_model=list[UsuarioOut], summary="Listar usuarios")
def listar_usuarios(rol: RolNombre | None = None, programa_id: int | None = None,
                    db: Session = Depends(get_db), usuario: Usuario = Depends(admin_o_coord)):
    q = filtrar_usuarios(db, usuario, select(Usuario))
    if rol:
        q = q.where(Usuario.rol.has(nombre=rol))
    if programa_id:
        q = q.where(Usuario.programa_id == programa_id)
    return [_usuario_out(u) for u in db.scalars(q.order_by(Usuario.nombre))]


@router.post("/usuarios", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED,
             summary="Crear usuario")
def crear_usuario(datos: UsuarioCrear, db: Session = Depends(get_db),
                  _: Usuario = Depends(solo_admin)):
    rol = db.scalar(select(Rol).where(Rol.nombre == datos.rol))
    if rol is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"El rol {datos.rol} no existe")
    usuario = Usuario(
        documento=datos.documento, nombre=datos.nombre, correo=datos.correo,
        password_hash=hash_password(datos.password), rol_id=rol.id,
        programa_id=datos.programa_id,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Ya existe un usuario con ese documento o correo")
    db.refresh(usuario)
    return _usuario_out(usuario)


# ----------------------------- Programas y asignaturas -----------------------------
@router.get("/programas", response_model=list[ProgramaOut], summary="Listar programas")
def listar_programas(db: Session = Depends(get_db),
                     usuario: Usuario = Depends(usuario_actual)):
    q = select(Programa).order_by(Programa.nombre)
    visibles = programas_de(db, usuario)
    if visibles is not None:
        q = q.where(Programa.id.in_(visibles))
    return list(db.scalars(q))


@router.post("/programas", response_model=ProgramaOut, status_code=status.HTTP_201_CREATED,
             summary="Crear programa")
def crear_programa(datos: ProgramaCrear, db: Session = Depends(get_db),
                   _: Usuario = Depends(solo_admin)):
    programa = Programa(**datos.model_dump())
    db.add(programa)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un programa con ese código")
    db.refresh(programa)
    return programa


@router.get("/asignaturas", response_model=list[AsignaturaOut], summary="Listar asignaturas")
def listar_asignaturas(programa_id: int | None = None, db: Session = Depends(get_db),
                       usuario: Usuario = Depends(usuario_actual)):
    """Un docente solo ve las asignaturas en las que tiene estudiantes a cargo."""
    q = select(Asignatura)
    if programa_id:
        q = q.where(Asignatura.programa_id == programa_id)
    if usuario.rol.nombre == RolNombre.DOCENTE:
        suyas = select(Matricula.asignatura_id).where(Matricula.docente_id == usuario.id)
        q = q.where(Asignatura.id.in_(suyas))
    else:
        visibles = programas_de(db, usuario)
        if visibles is not None:
            q = q.where(Asignatura.programa_id.in_(visibles))
    return list(db.scalars(q.order_by(Asignatura.nombre)))


@router.post("/asignaturas", response_model=AsignaturaOut, status_code=status.HTTP_201_CREATED,
             summary="Crear asignatura")
def crear_asignatura(datos: AsignaturaCrear, db: Session = Depends(get_db),
                     _: Usuario = Depends(solo_admin)):
    asignatura = Asignatura(**datos.model_dump())
    db.add(asignatura)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una asignatura con ese código")
    db.refresh(asignatura)
    return asignatura


# ----------------------------- Modelo de riesgo (RQF-02) -----------------------------
@router.get("/factores", response_model=list[FactorOut], summary="Factores vigentes del modelo")
def listar_factores(todos: bool = False, db: Session = Depends(get_db)):
    q = select(FactorRiesgo)
    if not todos:
        q = q.where(FactorRiesgo.vigente.is_(True))
    return list(db.scalars(q.order_by(FactorRiesgo.version_modelo.desc(), FactorRiesgo.peso.desc())))


@router.put("/factores", response_model=list[FactorOut], summary="Configurar pesos del modelo")
def configurar_modelo(datos: ConfigurarModelo, db: Session = Depends(get_db),
                      _: Usuario = Depends(solo_admin)):
    """RQF-02. La suma de los pesos debe ser exactamente 100%.

    La configuración anterior no se borra: se marca como no vigente y la nueva
    entra con una versión incrementada, para que las evaluaciones antiguas
    sigan siendo reproducibles.
    """
    total = round(sum(f.peso for f in datos.factores), 2)
    if total != 100.0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Los pesos suman {total}%, deben sumar exactamente 100%. "
            "No se aplicó ningún cambio.")

    desconocidos = [f.codigo for f in datos.factores if f.codigo not in CALCULADORES]
    if desconocidos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Estos factores no tienen fórmula implementada: {', '.join(desconocidos)}")

    vigentes = list(db.scalars(select(FactorRiesgo).where(FactorRiesgo.vigente.is_(True))))
    nombres = {f.codigo: f.nombre for f in vigentes}
    version = (max((f.version_modelo for f in vigentes), default=0)) + 1
    for f in vigentes:
        f.vigente = False
    for f in datos.factores:
        db.add(FactorRiesgo(
            codigo=f.codigo, nombre=f.nombre or nombres.get(f.codigo, f.codigo),
            peso=f.peso, version_modelo=version, vigente=True))
    db.commit()
    return list(db.scalars(select(FactorRiesgo).where(FactorRiesgo.vigente.is_(True))
                           .order_by(FactorRiesgo.peso.desc())))


# ----------------------------- Auditoría (RQNF-03) -----------------------------
@router.get("/bitacora", response_model=list[BitacoraOut], summary="Bitácora de accesos sensibles")
def bitacora(limite: int = 200, recurso: str | None = None,
             accion: AccionAuditoria | None = None, db: Session = Depends(get_db),
             _: Usuario = Depends(admin_o_coord)):
    q = select(BitacoraAcceso)
    if recurso:
        q = q.where(BitacoraAcceso.recurso == recurso)
    if accion:
        q = q.where(BitacoraAcceso.accion == accion)
    permitidos = estudiantes_de(db, _)
    if permitidos is not None:
        casos = select(CasoAcompanamiento.id).where(
            CasoAcompanamiento.estudiante_id.in_(permitidos))
        q = q.where((BitacoraAcceso.recurso != "CASO")
                    | BitacoraAcceso.recurso_id.in_(casos))
    filas = db.scalars(q.order_by(BitacoraAcceso.id.desc()).limit(limite))
    salida = []
    for f in filas:
        usuario = db.get(Usuario, f.usuario_id)
        salida.append({"id": f.id, "usuario": usuario.nombre if usuario else "—",
                       "recurso": f.recurso, "recurso_id": f.recurso_id,
                       "accion": f.accion, "detalle": f.detalle, "fecha": f.fecha})
    return salida


def _usuario_out(u: Usuario) -> dict:
    return {"id": u.id, "documento": u.documento, "nombre": u.nombre, "correo": u.correo,
            "rol": u.rol.nombre, "programa_id": u.programa_id, "activo": u.activo}
