"""Carga de datos de demostración.

Uso:  python -m app.seed [--reset]

Crea programas, usuarios de los seis roles, estudiantes con desempeño variado y
ejecuta el motor de riesgo sobre toda la población, de modo que al abrir la
aplicación ya haya alertas, casos asignados y un caso escalado.
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import (
    Asignatura, CasoAcompanamiento, Derivacion, EstadoCaso, EstadoMatricula,
    Estudiante, FactorRiesgo, Inasistencia, Intervencion, Matricula, Nota,
    Programa, Rol, RolNombre, TipoApoyo, TipoIntervencion, Usuario,
)
from .security import hash_password
from .services import casos as servicio_casos
from .config import CORTE_VIGENTE
from .services.riesgo import PERIODO_VIGENTE, evaluar_y_atender

CLAVE_DEMO = "sara2026"
random.seed(20262)

FACTORES = [
    ("RENDIMIENTO", "Rendimiento del corte", 35),
    ("INASISTENCIA", "Inasistencia", 25),
    ("REPETIDAS", "Asignaturas repetidas", 20),
    ("FINANCIERA", "Situación financiera", 10),
    ("HISTORICO", "Rendimiento histórico", 10),
]

PROGRAMAS = [
    ("ISC", "Ingeniería de Sistemas y Computación"),
    ("IIN", "Ingeniería Industrial"),
    ("PSI", "Psicología"),
    ("DER", "Derecho"),
]

NOMBRES = [
    "Daniela Ortiz Mendoza", "Mateo Restrepo Gil", "Valentina Gómez Ruiz",
    "Samuel Pérez Lara", "Camila Núñez Soto", "Andrés Mejía Vargas",
    "Sofía Cárdenas Peña", "Julián Vargas Mora", "Isabella Mora Díaz",
    "Tomás Vélez Cano", "Laura Hoyos Ríos", "Nicolás Vera Pardo",
    "Mariana Ruiz Salas", "Luis Parra Nieto", "Juliana Serna Olaya",
    "Emilio Castaño Vega", "Antonia Rojas Lema", "Sebastián Lima Cruz",
    "Paula Jiménez Arias", "Felipe Duarte Rangel", "Sara Benítez Cuervo",
    "Martín Olarte Gaitán", "Gabriela Pinto Lozano", "Simón Aguirre Rico",
    "Manuela Quintero Bravo", "Jerónimo Salas Mesa", "Luciana Bedoya Cera",
    "Alejandro Niño Pinilla", "Renata Zapata Correa", "Esteban Molina Vidal",
]

ASIGNATURAS = {
    "ISC": [("ISC301", "Cálculo III", 4), ("ISC310", "Bases de Datos", 3), ("ISC320", "Diseño de Software I", 3)],
    "IIN": [("IIN205", "Investigación de Operaciones", 4), ("IIN210", "Procesos Industriales", 3), ("IIN220", "Estadística II", 3)],
    "PSI": [("PSI150", "Psicología Cognitiva", 3), ("PSI160", "Métodos Cuantitativos", 4), ("PSI170", "Psicometría", 3)],
    "DER": [("DER120", "Derecho Constitucional", 4), ("DER130", "Derecho Penal", 3), ("DER140", "Obligaciones", 3)],
}


def _usuario(db, documento, nombre, correo, rol_id, programa_id=None) -> Usuario:
    u = Usuario(documento=documento, nombre=nombre, correo=correo,
                password_hash=hash_password(CLAVE_DEMO), rol_id=rol_id,
                programa_id=programa_id)
    db.add(u)
    db.flush()
    return u


def sembrar(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.scalar(select(Usuario).limit(1)) is not None:
            print("La base ya tiene datos. Usa --reset para volver a sembrarla.")
            return

        roles = {}
        for nombre in RolNombre:
            rol = Rol(nombre=nombre)
            db.add(rol)
            db.flush()
            roles[nombre] = rol.id

        for codigo, nombre, peso in FACTORES:
            db.add(FactorRiesgo(codigo=codigo, nombre=nombre, peso=peso,
                                version_modelo=1, vigente=True))
        db.flush()

        admin = _usuario(db, "1000000001", "Administrador SARA", "admin@uninorte.edu.co",
                         roles[RolNombre.ADMINISTRADOR])
        bienestar = _usuario(db, "1000000002", "Paola Restrepo", "bienestar@uninorte.edu.co",
                             roles[RolNombre.BIENESTAR])

        programas, consejeros, docentes = {}, {}, {}
        for i, (codigo, nombre) in enumerate(PROGRAMAS):
            programa = Programa(codigo=codigo, nombre=nombre, semestres_totales=10)
            db.add(programa)
            db.flush()
            programas[codigo] = programa

            coord = _usuario(db, f"20000000{i}1", f"Laura Sánchez ({codigo})",
                             f"coord.{codigo.lower()}@uninorte.edu.co",
                             roles[RolNombre.COORDINADOR], programa.id)
            programa.coordinador_id = coord.id

            consejeros[codigo] = [
                _usuario(db, f"30000000{i}{j}", nom, f"{correo}.{codigo.lower()}@uninorte.edu.co",
                         roles[RolNombre.CONSEJERO], programa.id)
                for j, (nom, correo) in enumerate([("Juan Pérez", "juan"), ("Ana Gil", "ana")])
            ]
            docentes[codigo] = [
                _usuario(db, f"40000000{i}{j}", nom, f"{correo}.{codigo.lower()}@uninorte.edu.co",
                         roles[RolNombre.DOCENTE], programa.id)
                for j, (nom, correo) in enumerate([("Carlos Medina", "carlos"), ("Elena Ramos", "elena")])
            ]
            for cod_asig, nom_asig, creditos in ASIGNATURAS[codigo]:
                db.add(Asignatura(codigo=cod_asig, nombre=nom_asig,
                                  programa_id=programa.id, creditos=creditos))
        db.flush()

        # --- Estudiantes -------------------------------------------------
        # El primero reproduce el caso del prototipo: índice crítico.
        perfiles = [("critico", 3), ("alto", 6), ("medio", 8), ("bajo", 13)]
        plan = [p for p, n in perfiles for _ in range(n)]

        hoy = date.today()
        for idx, nombre in enumerate(NOMBRES):
            perfil = plan[idx] if idx < len(plan) else "bajo"
            codigo = PROGRAMAS[idx % len(PROGRAMAS)][0]
            programa = programas[codigo]
            documento = f"5{idx:09d}"
            correo = nombre.lower().split()[0] + f".{idx}@uninorte.edu.co"
            usuario = _usuario(db, documento, nombre, correo, roles[RolNombre.ESTUDIANTE], programa.id)

            if perfil == "critico":
                promedio_acum, apoyo, deuda, repetidas = 2.5, False, True, 3
                nota_rango, faltas_pct, tendencia = (1.4, 2.4), 0.80, -0.35
            elif perfil == "alto":
                promedio_acum, apoyo, deuda, repetidas = 2.9, False, True, 2
                nota_rango, faltas_pct, tendencia = (2.3, 3.0), 0.45, -0.25
            elif perfil == "medio":
                promedio_acum, apoyo, deuda, repetidas = 3.1, False, False, 1
                nota_rango, faltas_pct, tendencia = (3.0, 3.5), 0.28, -0.15
            else:
                promedio_acum, apoyo, deuda, repetidas = 4.1, True, False, 0
                nota_rango, faltas_pct, tendencia = (3.6, 4.8), 0.05, 0.05

            est = Estudiante(usuario_id=usuario.id, programa_id=programa.id,
                             semestre=random.randint(3, 8), promedio_acumulado=promedio_acum,
                             estado_matricula=EstadoMatricula.ACTIVA,
                             tiene_apoyo_financiero=apoyo, tiene_deuda_vigente=deuda)
            db.add(est)
            db.flush()

            asignaturas = list(db.scalars(
                select(Asignatura).where(Asignatura.programa_id == programa.id)))
            for k, asignatura in enumerate(asignaturas):
                docente = docentes[codigo][k % len(docentes[codigo])]
                sesiones = 18
                matricula = Matricula(
                    estudiante_id=est.id, asignatura_id=asignatura.id, docente_id=docente.id,
                    periodo=PERIODO_VIGENTE, numero_intento=2 if k < repetidas else 1,
                    sesiones_programadas=sesiones)
                db.add(matricula)
                db.flush()
                # Una nota por cada corte del semestre. Los perfiles en riesgo
                # arrastran una tendencia a la baja; los demás se mantienen.
                for corte in range(1, CORTE_VIGENTE + 1):
                    deriva = tendencia * (corte - 1)
                    piso, techo = nota_rango
                    valor = random.uniform(piso, techo) + deriva
                    db.add(Nota(matricula_id=matricula.id, corte=corte,
                                valor=round(min(5.0, max(0.0, valor)), 1),
                                registrada_por=docente.id))
                faltas = int(sesiones * faltas_pct)
                for f in range(faltas):
                    db.add(Inasistencia(matricula_id=matricula.id,
                                        fecha_sesion=hoy - timedelta(days=f * 2 + k),
                                        justificada=False, registrada_por=docente.id))
        db.commit()

        # --- Motor de riesgo sobre toda la población ---------------------
        estudiantes = list(db.scalars(select(Estudiante)))
        for corte in range(1, CORTE_VIGENTE + 1):
            for est in estudiantes:
                evaluar_y_atender(db, est, corte=corte)

        # --- Historia de acompañamiento para que la demo tenga vida ------
        abiertos = list(db.scalars(
            select(CasoAcompanamiento)
            .where(CasoAcompanamiento.estado == EstadoCaso.ASIGNADO)
            .order_by(CasoAcompanamiento.id)))

        # Un caso con intervención, compromisos, cita y derivación abierta.
        if abiertos:
            caso = abiertos[0]
            inter = Intervencion(
                caso_id=caso.id, consejero_id=caso.consejero_id,
                tipo=TipoIntervencion.ENTREVISTA,
                descripcion=("La estudiante reporta dificultades para cubrir el transporte y "
                             "está faltando a las primeras horas de clase. Se acuerda solicitar "
                             "apoyo de bienestar y reorganizar el horario del próximo corte."),
                compromisos=("Asistir a todas las clases hasta el cierre del corte 3. "
                             "Radicar la solicitud de apoyo de transporte."),
                fecha_cita=datetime.now() + timedelta(days=4))
            db.add(inter)
            db.flush()
            servicio_casos.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO,
                                          usuario=None, motivo="PRIMERA_INTERVENCION")
            db.add(Derivacion(caso_id=caso.id, tipo_apoyo=TipoApoyo.FINANCIERO,
                              solicitada_por=caso.consejero_id,
                              observacion="Requiere apoyo de transporte para el corte 3."))
            db.commit()

        # Un caso crítico abierto hace tiempo y sin intervención: queda escalable.
        criticos = [c for c in abiertos[1:] if c.nivel_apertura.value == "CRITICO"]
        if criticos:
            viejo = criticos[0]
            viejo.fecha_apertura = datetime.now() - timedelta(days=9)
            db.commit()
            from .services.escalamiento import revisar_casos_criticos
            resumen = revisar_casos_criticos(db)
            print(f"  escalamientos aplicados: {resumen['escalados']}")

        total_casos = db.scalar(select(Estudiante).limit(1)) and len(
            list(db.scalars(select(CasoAcompanamiento))))
        print("Datos de demostración cargados.")
        print(f"  programas: {len(PROGRAMAS)} | estudiantes: {len(estudiantes)} | casos: {total_casos}")
        _imprimir_credenciales(db)
    finally:
        db.close()


ALCANCE_POR_ROL = {
    RolNombre.ADMINISTRADOR: "toda la institución; configura el modelo de riesgo",
    RolNombre.COORDINADOR: "su propio programa: riesgo, casos, indicadores y bitácora",
    RolNombre.CONSEJERO: "solo los estudiantes de los casos que tiene asignados",
    RolNombre.BIENESTAR: "las derivaciones que le llegan; indicadores institucionales",
    RolNombre.DOCENTE: "solo las asignaturas que dicta",
    RolNombre.ESTUDIANTE: "solo su propia ficha, sus notas y sus compromisos",
}
ORDEN_ROLES = [RolNombre.ADMINISTRADOR, RolNombre.COORDINADOR, RolNombre.CONSEJERO,
               RolNombre.BIENESTAR, RolNombre.DOCENTE, RolNombre.ESTUDIANTE]


def _imprimir_credenciales(db: Session) -> None:
    """Deja en pantalla con qué usuario entrar para probar cada rol."""
    print()
    print("  " + "=" * 92)
    print(f"  USUARIOS DE DEMOSTRACIÓN · la clave de todos es: {CLAVE_DEMO}")
    print("  " + "=" * 92)
    for nombre_rol in ORDEN_ROLES:
        usuarios = list(db.scalars(
            select(Usuario).join(Usuario.rol)
            .where(Usuario.rol.has(nombre=nombre_rol))
            .order_by(Usuario.id)))
        if not usuarios:
            continue
        print(f"\n  {nombre_rol.value}  —  ve {ALCANCE_POR_ROL[nombre_rol]}")
        for u in usuarios[:4]:
            programa = u.programa.nombre if u.programa else "—"
            print(f"     {u.correo:<34} {u.nombre:<26} {programa}")
        if len(usuarios) > 4:
            print(f"     … y {len(usuarios) - 4} más del mismo rol")
    print("  " + "=" * 92)
    print("  Sugerencia: entra con el coordinador y con el consejero del mismo programa")
    print("  para ver la diferencia de alcance sobre los mismos casos.")
    print()


if __name__ == "__main__":
    sembrar(reset="--reset" in sys.argv)
