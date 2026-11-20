"""Configuración común de las pruebas: base en memoria y cliente de API."""
import os
from datetime import date, timedelta

os.environ["SARA_SCHEDULER"] = "0"
os.environ["SARA_BCRYPT_ROUNDS"] = "4"   # las pruebas no necesitan 12 rondas

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.config import CORTE_VIGENTE
from app.models import (
    Asignatura, Estudiante, FactorRiesgo, Inasistencia, Matricula, Nota, Programa,
    Rol, RolNombre, Usuario,
)
from app.security import hash_password

CLAVE = "pruebas2026"

engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                       poolclass=StaticPool, future=True)
Sesion = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    sesion = Sesion()
    try:
        _datos_base(sesion)
        yield sesion
    finally:
        sesion.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def _get_db():
        yield db
    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def token(client, correo: str) -> dict:
    r = client.post("/api/auth/login", data={"username": correo, "password": CLAVE})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _usuario(db, documento, nombre, correo, rol_id, programa_id=None) -> Usuario:
    u = Usuario(documento=documento, nombre=nombre, correo=correo,
                password_hash=hash_password(CLAVE), rol_id=rol_id, programa_id=programa_id)
    db.add(u)
    db.flush()
    return u


def _datos_base(db):
    """Un programa, un usuario de cada rol, dos estudiantes y una asignatura."""
    roles = {}
    for nombre in RolNombre:
        rol = Rol(nombre=nombre)
        db.add(rol)
        db.flush()
        roles[nombre] = rol.id

    for codigo, nombre, peso in [
        ("RENDIMIENTO", "Rendimiento del corte", 35), ("INASISTENCIA", "Inasistencia", 25),
        ("REPETIDAS", "Asignaturas repetidas", 20), ("FINANCIERA", "Situación financiera", 10),
        ("HISTORICO", "Rendimiento histórico", 10),
    ]:
        db.add(FactorRiesgo(codigo=codigo, nombre=nombre, peso=peso, version_modelo=1, vigente=True))
    db.flush()

    programa = Programa(codigo="ISC", nombre="Ingeniería de Sistemas", semestres_totales=10)
    db.add(programa)
    db.flush()

    admin = _usuario(db, "1", "Admin", "admin@u.edu.co", roles[RolNombre.ADMINISTRADOR])
    coord = _usuario(db, "2", "Coordinadora", "coord@u.edu.co", roles[RolNombre.COORDINADOR], programa.id)
    programa.coordinador_id = coord.id
    _usuario(db, "3", "Consejero Uno", "consejero1@u.edu.co", roles[RolNombre.CONSEJERO], programa.id)
    _usuario(db, "4", "Consejero Dos", "consejero2@u.edu.co", roles[RolNombre.CONSEJERO], programa.id)
    docente = _usuario(db, "5", "Docente", "docente@u.edu.co", roles[RolNombre.DOCENTE], programa.id)
    _usuario(db, "6", "Docente Ajeno", "otro@u.edu.co", roles[RolNombre.DOCENTE], programa.id)
    _usuario(db, "7", "Bienestar", "bienestar@u.edu.co", roles[RolNombre.BIENESTAR])

    asignaturas = []
    for codigo, nombre in [("ISC1", "Cálculo III"), ("ISC2", "Bases de Datos")]:
        a = Asignatura(codigo=codigo, nombre=nombre, programa_id=programa.id, creditos=4)
        db.add(a)
        db.flush()
        asignaturas.append(a)

    # Estudiante en riesgo (promedio bajo, sin apoyo, con deuda) y estudiante sano.
    for i, (nombre, correo, acum, apoyo, deuda, sesiones) in enumerate([
        ("Estudiante Riesgo", "riesgo@u.edu.co", 2.4, False, True, 20),
        ("Estudiante Sano", "sano@u.edu.co", 4.3, True, False, 20),
    ]):
        usuario = _usuario(db, f"10{i}", nombre, correo, roles[RolNombre.ESTUDIANTE], programa.id)
        est = Estudiante(usuario_id=usuario.id, programa_id=programa.id, semestre=5,
                         promedio_acumulado=acum, tiene_apoyo_financiero=apoyo,
                         tiene_deuda_vigente=deuda)
        db.add(est)
        db.flush()
        if i == 0:
            # Estudiante en riesgo: dos asignaturas repetidas, notas bajas y mucha
            # inasistencia, de modo que el índice quede en nivel Alto o Crítico.
            for k, asignatura in enumerate(asignaturas):
                matricula = Matricula(estudiante_id=est.id, asignatura_id=asignatura.id,
                                      docente_id=docente.id, periodo="2026-2",
                                      numero_intento=2, sesiones_programadas=sesiones)
                db.add(matricula)
                db.flush()
                for corte in range(1, CORTE_VIGENTE + 1):
                    db.add(Nota(matricula_id=matricula.id, corte=corte, valor=1.0,
                                registrada_por=docente.id))
                for f in range(16):
                    db.add(Inasistencia(matricula_id=matricula.id,
                                        fecha_sesion=date(2026, 9, 1) + timedelta(days=f + k * 20),
                                        justificada=False, registrada_por=docente.id))
        else:
            db.add(Matricula(estudiante_id=est.id, asignatura_id=asignaturas[0].id,
                             docente_id=docente.id, periodo="2026-2", numero_intento=1,
                             sesiones_programadas=sesiones))
    db.commit()


def estudiante_por_correo(db, correo: str) -> Estudiante:
    usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
    return db.scalar(select(Estudiante).where(Estudiante.usuario_id == usuario.id))


def matricula_de(db, est: Estudiante) -> Matricula:
    return db.scalar(select(Matricula).where(Matricula.estudiante_id == est.id))
