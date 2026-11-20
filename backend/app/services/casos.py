"""Casos de acompañamiento: apertura, asignación y máquina de estados.

Reglas implementadas: RN-03, RN-04, RN-05, RN-08, RN-09 y RQF-07, RQF-08, RQF-12.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import MAX_CASOS_ACTIVOS_POR_CONSEJERO
from ..models import (
    CasoAcompanamiento, Derivacion, EstadoCaso, EstadoDerivacion, Estudiante,
    EvaluacionRiesgo, HistorialEstadoCaso, Intervencion, NivelRiesgo,
    ResultadoCaso, RolNombre, Usuario,
)
from .notificaciones import notificar

ESTADOS_ACTIVOS = (
    EstadoCaso.ABIERTO, EstadoCaso.ASIGNADO,
    EstadoCaso.EN_SEGUIMIENTO, EstadoCaso.EN_EVALUACION,
)

# RN-05: desde cada estado, a cuáles se puede pasar.
TRANSICIONES: dict[EstadoCaso, set[EstadoCaso]] = {
    EstadoCaso.ABIERTO: {EstadoCaso.ASIGNADO},
    EstadoCaso.ASIGNADO: {EstadoCaso.EN_SEGUIMIENTO},
    EstadoCaso.EN_SEGUIMIENTO: {EstadoCaso.EN_EVALUACION},
    # El coordinador puede devolver el caso a seguimiento si no está concluido.
    EstadoCaso.EN_EVALUACION: {EstadoCaso.CERRADO, EstadoCaso.EN_SEGUIMIENTO},
    EstadoCaso.CERRADO: set(),
}


class ErrorCaso(Exception):
    """Violación de una regla de negocio sobre los casos."""


# --------------------------------------------------------------------------
# Transiciones de estado
# --------------------------------------------------------------------------
def cambiar_estado(db: Session, caso: CasoAcompanamiento, nuevo: EstadoCaso,
                   usuario: Usuario | None = None, motivo: str | None = None) -> None:
    """Único punto por el que cambia el estado de un caso (RQF-12)."""
    anterior = caso.estado
    if nuevo not in TRANSICIONES[anterior]:
        raise ErrorCaso(
            f"Transición no permitida: {anterior.value} → {nuevo.value}. "
            f"Desde {anterior.value} solo se puede pasar a "
            f"{', '.join(e.value for e in TRANSICIONES[anterior]) or 'ningún estado'}."
        )
    caso.estado = nuevo
    db.add(HistorialEstadoCaso(
        caso_id=caso.id, estado_anterior=anterior, estado_nuevo=nuevo,
        motivo=motivo, usuario_id=usuario.id if usuario else None,
    ))
    db.flush()


# --------------------------------------------------------------------------
# Apertura y asignación
# --------------------------------------------------------------------------
def caso_abierto_de(db: Session, estudiante_id: int) -> CasoAcompanamiento | None:
    """RN-09: un estudiante no puede tener dos casos abiertos a la vez."""
    return db.scalar(
        select(CasoAcompanamiento)
        .where(CasoAcompanamiento.estudiante_id == estudiante_id,
               CasoAcompanamiento.estado.in_(ESTADOS_ACTIVOS))
        .order_by(CasoAcompanamiento.id.desc())
    )


def casos_activos_de(db: Session, consejero_id: int) -> int:
    return db.scalar(
        select(func.count(CasoAcompanamiento.id))
        .where(CasoAcompanamiento.consejero_id == consejero_id,
               CasoAcompanamiento.estado.in_(ESTADOS_ACTIVOS))
    ) or 0


def consejero_con_menos_casos(db: Session, programa_id: int) -> Usuario | None:
    """RN-04: el consejero del programa con menos casos activos, con tope de 20."""
    consejeros = list(db.scalars(
        select(Usuario).join(Usuario.rol)
        .where(Usuario.programa_id == programa_id, Usuario.activo.is_(True))
        .where(Usuario.rol.has(nombre=RolNombre.CONSEJERO))
    ))
    disponibles = [(casos_activos_de(db, c.id), c.id, c) for c in consejeros]
    disponibles = [d for d in disponibles if d[0] < MAX_CASOS_ACTIVOS_POR_CONSEJERO]
    if not disponibles:
        return None
    disponibles.sort(key=lambda d: (d[0], d[1]))   # menos casos; desempate por id
    return disponibles[0][2]


def abrir_o_adjuntar(db: Session, estudiante: Estudiante,
                     evaluacion: EvaluacionRiesgo) -> tuple[CasoAcompanamiento, bool]:
    """RN-03 + RN-09. Devuelve (caso, se_creó_uno_nuevo)."""
    vigente = caso_abierto_de(db, estudiante.id)
    if vigente is not None:
        # La alerta se adjunta al caso existente; si subió de nivel, se deja constancia.
        if _gravedad(evaluacion.nivel) > _gravedad(vigente.nivel_apertura):
            vigente.nivel_apertura = evaluacion.nivel
            notificar(db, vigente.consejero_id, "ALERTA_RIESGO",
                      f"El caso #{vigente.id} subió a nivel {evaluacion.nivel.value}", vigente.id)
        db.flush()
        return vigente, False

    caso = CasoAcompanamiento(
        estudiante_id=estudiante.id, evaluacion_id=evaluacion.id,
        nivel_apertura=evaluacion.nivel, estado=EstadoCaso.ABIERTO,
    )
    db.add(caso)
    db.flush()
    db.add(HistorialEstadoCaso(
        caso_id=caso.id, estado_anterior=None, estado_nuevo=EstadoCaso.ABIERTO,
        motivo="APERTURA_AUTOMATICA", usuario_id=None,
    ))
    db.flush()
    asignar_automaticamente(db, caso)
    return caso, True


def abrir_manualmente(db: Session, estudiante: Estudiante, quien: Usuario,
                      motivo: str, consejero: Usuario | None = None) -> CasoAcompanamiento:
    """RQF-08: el coordinador abre un caso sin esperar a que el índice lo dispare.

    Sirve para lo que el modelo no ve: un reporte de un docente, una situación
    familiar, una señal de alerta en clase. Igual que en la apertura automática,
    se respeta RN-09 (un solo caso activo por estudiante).
    """
    from .riesgo import evaluar   # import diferido

    if caso_abierto_de(db, estudiante.id) is not None:
        raise ErrorCaso("El estudiante ya tiene un caso activo; no se puede abrir otro")
    if not motivo or len(motivo.strip()) < 10:
        raise ErrorCaso("La apertura manual exige un motivo de al menos 10 caracteres")

    evaluacion = evaluar(db, estudiante, commit=False)
    caso = CasoAcompanamiento(
        estudiante_id=estudiante.id, evaluacion_id=evaluacion.id,
        nivel_apertura=evaluacion.nivel, estado=EstadoCaso.ABIERTO,
    )
    db.add(caso)
    db.flush()
    db.add(HistorialEstadoCaso(
        caso_id=caso.id, estado_anterior=None, estado_nuevo=EstadoCaso.ABIERTO,
        motivo="APERTURA_MANUAL", usuario_id=quien.id,
    ))
    db.flush()

    if consejero is not None:
        if casos_activos_de(db, consejero.id) >= MAX_CASOS_ACTIVOS_POR_CONSEJERO:
            raise ErrorCaso(
                f"{consejero.nombre} ya tiene {MAX_CASOS_ACTIVOS_POR_CONSEJERO} casos activos")
        caso.consejero_id = consejero.id
        cambiar_estado(db, caso, EstadoCaso.ASIGNADO, usuario=quien, motivo="ASIGNACION_MANUAL")
        notificar(db, consejero.id, "CASO_ASIGNADO",
                  f"{quien.nombre} te asignó el caso #{caso.id}", caso.id)
    else:
        asignar_automaticamente(db, caso)
    db.flush()
    return caso


def reabrir(db: Session, caso: CasoAcompanamiento, quien: Usuario, motivo: str) -> None:
    """Acción de supervisión del coordinador: un caso cerrado vuelve a seguimiento.

    No pasa por `cambiar_estado` porque la máquina de estados no permite salir de
    CERRADO: es una excepción deliberada, restringida al coordinador y registrada
    como tal en el historial y en la bitácora.
    """
    if caso.estado != EstadoCaso.CERRADO:
        raise ErrorCaso("Solo se puede reabrir un caso cerrado")
    if not motivo or len(motivo.strip()) < 10:
        raise ErrorCaso("La reapertura exige un motivo de al menos 10 caracteres")

    caso.estado = EstadoCaso.EN_SEGUIMIENTO
    caso.resultado = None
    caso.fecha_cierre = None
    caso.indice_cierre = None
    db.add(HistorialEstadoCaso(
        caso_id=caso.id, estado_anterior=EstadoCaso.CERRADO,
        estado_nuevo=EstadoCaso.EN_SEGUIMIENTO, motivo="REAPERTURA", usuario_id=quien.id,
    ))
    if caso.consejero_id:
        notificar(db, caso.consejero_id, "CASO_REABIERTO",
                  f"{quien.nombre} reabrió el caso #{caso.id}: {motivo.strip()}", caso.id)
    db.flush()


def atender_escalamiento(db: Session, caso: CasoAcompanamiento, quien: Usuario) -> None:
    """El coordinador toma el caso escalado: deja de figurar como pendiente."""
    if not caso.escalado:
        raise ErrorCaso("Este caso no está escalado")
    caso.escalado = False
    db.add(HistorialEstadoCaso(
        caso_id=caso.id, estado_anterior=caso.estado, estado_nuevo=caso.estado,
        motivo="ESCALAMIENTO_ATENDIDO", usuario_id=quien.id,
    ))
    if caso.consejero_id:
        notificar(db, caso.consejero_id, "ESCALAMIENTO",
                  f"{quien.nombre} tomó el escalamiento del caso #{caso.id}", caso.id)
    db.flush()


def asignar_automaticamente(db: Session, caso: CasoAcompanamiento) -> Usuario | None:
    """RQF-08. Si ningún consejero tiene cupo, se avisa al coordinador."""
    programa = caso.estudiante.programa
    consejero = consejero_con_menos_casos(db, programa.id)
    if consejero is None:
        notificar(db, programa.coordinador_id, "CASO_SIN_CONSEJERO",
                  f"El caso #{caso.id} no pudo asignarse: ningún consejero tiene cupo",
                  caso.id)
        db.flush()
        return None
    caso.consejero_id = consejero.id
    cambiar_estado(db, caso, EstadoCaso.ASIGNADO, usuario=None, motivo="ASIGNACION_AUTOMATICA")
    notificar(db, consejero.id, "CASO_ASIGNADO",
              f"Nuevo caso #{caso.id} de nivel {caso.nivel_apertura.value} asignado", caso.id)
    return consejero


def reasignar(db: Session, caso: CasoAcompanamiento, consejero: Usuario, quien: Usuario) -> None:
    """El coordinador reasigna un caso a otro consejero."""
    if consejero.rol.nombre != RolNombre.CONSEJERO:
        raise ErrorCaso("El usuario indicado no es un consejero")
    # El acompañamiento lo lleva alguien del mismo programa que el estudiante.
    if consejero.programa_id != caso.estudiante.programa_id:
        raise ErrorCaso(
            f"{consejero.nombre} no pertenece al programa del estudiante")
    if casos_activos_de(db, consejero.id) >= MAX_CASOS_ACTIVOS_POR_CONSEJERO:
        raise ErrorCaso(
            f"{consejero.nombre} ya tiene {MAX_CASOS_ACTIVOS_POR_CONSEJERO} casos activos")
    anterior = caso.consejero_id
    caso.consejero_id = consejero.id
    db.add(HistorialEstadoCaso(
        caso_id=caso.id, estado_anterior=caso.estado, estado_nuevo=caso.estado,
        motivo="REASIGNACION", usuario_id=quien.id,
    ))
    if caso.estado == EstadoCaso.ABIERTO:
        cambiar_estado(db, caso, EstadoCaso.ASIGNADO, usuario=quien, motivo="REASIGNACION")
    notificar(db, consejero.id, "CASO_ASIGNADO", f"Te reasignaron el caso #{caso.id}", caso.id)
    if anterior and anterior != consejero.id:
        notificar(db, anterior, "CASO_REASIGNADO", f"El caso #{caso.id} pasó a otro consejero", caso.id)
    db.flush()


# --------------------------------------------------------------------------
# Cierre
# --------------------------------------------------------------------------
def cerrar(db: Session, caso: CasoAcompanamiento, resultado: ResultadoCaso,
           usuario: Usuario) -> CasoAcompanamiento:
    """RN-08 + RQF-11: exige resultado, índice recalculado y derivaciones cerradas."""
    from .riesgo import evaluar   # import diferido

    puede = usuario.id == caso.consejero_id or usuario.rol.nombre == RolNombre.COORDINADOR
    if not puede:
        raise ErrorCaso("Solo el consejero asignado o el coordinador pueden cerrar un caso")

    abiertas = db.scalar(
        select(func.count(Derivacion.id))
        .where(Derivacion.caso_id == caso.id, Derivacion.estado == EstadoDerivacion.ABIERTA)
    ) or 0
    if abiertas:
        raise ErrorCaso(
            f"El caso tiene {abiertas} derivación(es) abierta(s) en bienestar; "
            "no se puede cerrar hasta que se atiendan")

    evaluacion = evaluar(db, caso.estudiante, commit=False)
    caso.resultado = resultado
    caso.indice_cierre = evaluacion.indice
    caso.fecha_cierre = datetime.now()
    cambiar_estado(db, caso, EstadoCaso.CERRADO, usuario=usuario, motivo="CIERRE")
    notificar(db, caso.estudiante.usuario_id, "CASO_CERRADO",
              f"Tu acompañamiento se cerró con resultado {resultado.value}", caso.id)
    coordinador_id = caso.estudiante.programa.coordinador_id
    if coordinador_id and coordinador_id != usuario.id:
        notificar(db, coordinador_id, "CASO_CERRADO",
                  f"El caso #{caso.id} se cerró con resultado {resultado.value}", caso.id)
    db.flush()
    return caso


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
_ORDEN = {NivelRiesgo.BAJO: 0, NivelRiesgo.MEDIO: 1, NivelRiesgo.ALTO: 2, NivelRiesgo.CRITICO: 3}


def _gravedad(nivel: NivelRiesgo) -> int:
    return _ORDEN[nivel]


def tiene_intervenciones(db: Session, caso_id: int) -> bool:
    return bool(db.scalar(
        select(func.count(Intervencion.id)).where(Intervencion.caso_id == caso_id)
    ))
