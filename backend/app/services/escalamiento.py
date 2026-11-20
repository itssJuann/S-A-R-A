"""Escalamiento de casos críticos desatendidos (RN-06, RQF-13).

Un caso de nivel Crítico que no registre su primera intervención dentro de los
3 días hábiles siguientes a su apertura se escala al coordinador del programa.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import DIAS_HABILES_ESCALAMIENTO
from ..models import (
    CasoAcompanamiento, EstadoCaso, HistorialEstadoCaso, NivelRiesgo,
)
from .casos import ESTADOS_ACTIVOS, tiene_intervenciones
from .notificaciones import notificar

# Festivos colombianos del periodo académico. En producción se cargan de una tabla.
FESTIVOS: set[date] = {
    date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2),
    date(2026, 4, 3), date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8),
    date(2026, 6, 15), date(2026, 6, 29), date(2026, 7, 20), date(2026, 8, 7),
    date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 16),
    date(2026, 12, 8), date(2026, 12, 25),
}


def dias_habiles_entre(inicio: date, fin: date) -> int:
    """Cuenta los días hábiles transcurridos, sin contar el día de apertura."""
    if fin <= inicio:
        return 0
    dias, actual = 0, inicio
    while actual < fin:
        actual += timedelta(days=1)
        if actual.weekday() < 5 and actual not in FESTIVOS:
            dias += 1
    return dias


def revisar_casos_criticos(db: Session, hoy: date | None = None) -> dict:
    """Revisión programada. Devuelve un resumen de la ejecución."""
    hoy = hoy or date.today()
    candidatos = list(db.scalars(
        select(CasoAcompanamiento).where(
            CasoAcompanamiento.nivel_apertura == NivelRiesgo.CRITICO,
            CasoAcompanamiento.escalado.is_(False),
            CasoAcompanamiento.estado.in_(ESTADOS_ACTIVOS),
        )
    ))
    resumen = {"fecha": hoy.isoformat(), "revisados": len(candidatos), "escalados": 0, "casos": []}
    for caso in candidatos:
        if tiene_intervenciones(db, caso.id):
            continue
        dias = dias_habiles_entre(caso.fecha_apertura.date(), hoy)
        if dias <= DIAS_HABILES_ESCALAMIENTO:
            continue
        _escalar(db, caso, dias)
        resumen["escalados"] += 1
        resumen["casos"].append({"caso_id": caso.id, "dias_habiles": dias})
    db.commit()
    return resumen


def _escalar(db: Session, caso: CasoAcompanamiento, dias: int) -> None:
    caso.escalado = True
    db.add(HistorialEstadoCaso(
        caso_id=caso.id, estado_anterior=caso.estado, estado_nuevo=caso.estado,
        motivo="ESCALAMIENTO", usuario_id=None,
    ))
    coordinador_id = caso.estudiante.programa.coordinador_id
    notificar(db, coordinador_id, "ESCALAMIENTO",
              f"Caso crítico #{caso.id} sin atención hace {dias} días hábiles", caso.id)
    notificar(db, caso.consejero_id, "ESCALAMIENTO",
              f"Tu caso #{caso.id} fue escalado al coordinador por falta de atención", caso.id)
    db.flush()
