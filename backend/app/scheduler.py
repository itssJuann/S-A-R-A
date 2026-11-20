"""Actor temporizado del sistema (RN-06, RN-07).

Dos trabajos programados:
  - todos los días a las 6:00: revisar y escalar los casos críticos desatendidos;
  - al iniciar cada corte: recalcular el índice de toda la población.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal
from .services.escalamiento import revisar_casos_criticos
from .services.riesgo import reevaluar_poblacion

log = logging.getLogger("sara.scheduler")
_planificador: BackgroundScheduler | None = None


def tarea_escalamiento() -> None:
    db = SessionLocal()
    try:
        resumen = revisar_casos_criticos(db)
        log.info("Revisión de escalamientos: %s", resumen)
    except Exception:
        log.exception("Falló la revisión de escalamientos")
    finally:
        db.close()


def tarea_reevaluacion(corte: int = 1) -> None:
    db = SessionLocal()
    try:
        resumen = reevaluar_poblacion(db, corte=corte)
        log.info("Reevaluación de corte %s: %s", corte, resumen)
    except Exception:
        log.exception("Falló la reevaluación masiva")
    finally:
        db.close()


def iniciar_planificador() -> BackgroundScheduler | None:
    """Se llama al arrancar la API. Se desactiva con SARA_SCHEDULER=0 (y en tests)."""
    global _planificador
    if os.getenv("SARA_SCHEDULER", "1") != "1" or _planificador is not None:
        return _planificador
    _planificador = BackgroundScheduler(timezone="America/Bogota")
    _planificador.add_job(tarea_escalamiento, "cron", hour=6, minute=0, id="escalamiento")
    # Fechas de inicio de corte del periodo 2026-2.
    for corte, (mes, dia) in enumerate([(8, 10), (9, 21), (11, 2)], start=1):
        _planificador.add_job(tarea_reevaluacion, "cron", month=mes, day=dia, hour=5,
                              args=[corte], id=f"reevaluacion-corte-{corte}")
    _planificador.start()
    log.info("Planificador iniciado con %d trabajos", len(_planificador.get_jobs()))
    return _planificador
