"""Pruebas del escalamiento de casos críticos (RN-06, RQF-13)."""
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.models import Intervencion, NivelRiesgo, Notificacion, TipoIntervencion
from app.services.escalamiento import dias_habiles_entre, revisar_casos_criticos
from app.services.riesgo import evaluar_y_atender

from .conftest import estudiante_por_correo


def test_dias_habiles_salta_fines_de_semana():
    # Viernes 6 de noviembre de 2026 -> lunes 9: un solo día hábil.
    assert dias_habiles_entre(date(2026, 11, 6), date(2026, 11, 9)) == 1
    # Viernes -> viernes siguiente: 5 días hábiles.
    assert dias_habiles_entre(date(2026, 11, 6), date(2026, 11, 13)) == 5
    # Mismo día o fecha anterior: cero.
    assert dias_habiles_entre(date(2026, 11, 6), date(2026, 11, 6)) == 0
    assert dias_habiles_entre(date(2026, 11, 6), date(2026, 11, 5)) == 0


def test_dias_habiles_salta_festivos():
    # El 16 de noviembre de 2026 es festivo en Colombia.
    assert dias_habiles_entre(date(2026, 11, 13), date(2026, 11, 17)) == 1


def _caso_critico(db):
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    est.promedio_acumulado = 1.0            # fuerza nivel Crítico
    db.commit()
    caso = evaluar_y_atender(db, est)["caso"]
    assert caso.nivel_apertura is NivelRiesgo.CRITICO
    return caso


def test_no_escala_dentro_del_plazo(db):
    caso = _caso_critico(db)
    caso.fecha_apertura = datetime(2026, 11, 9, 8, 0)     # lunes
    db.commit()
    resumen = revisar_casos_criticos(db, hoy=date(2026, 11, 11))   # miércoles: 2 días hábiles
    assert resumen["escalados"] == 0
    assert caso.escalado is False


def test_escala_pasados_tres_dias_habiles(db):
    caso = _caso_critico(db)
    caso.fecha_apertura = datetime(2026, 11, 9, 8, 0)     # lunes
    db.commit()
    resumen = revisar_casos_criticos(db, hoy=date(2026, 11, 13))   # viernes: 4 días hábiles
    assert resumen["escalados"] == 1
    db.refresh(caso)
    assert caso.escalado is True
    motivos = [h.motivo for h in caso.historial]
    assert "ESCALAMIENTO" in motivos


def test_caso_con_intervencion_no_escala(db):
    """El escalamiento castiga la falta de atención, no la antigüedad."""
    caso = _caso_critico(db)
    caso.fecha_apertura = datetime(2026, 11, 2, 8, 0)
    db.add(Intervencion(caso_id=caso.id, consejero_id=caso.consejero_id,
                        tipo=TipoIntervencion.LLAMADA, descripcion="Primer contacto telefónico"))
    db.commit()
    resumen = revisar_casos_criticos(db, hoy=date(2026, 11, 13))
    assert resumen["escalados"] == 0


def test_escalamiento_notifica_a_coordinador_y_consejero(db):
    caso = _caso_critico(db)
    caso.fecha_apertura = datetime(2026, 11, 9, 8, 0)
    db.commit()
    revisar_casos_criticos(db, hoy=date(2026, 11, 13))
    avisos = db.scalars(select(Notificacion).where(Notificacion.tipo == "ESCALAMIENTO")).all()
    assert len(avisos) == 2
    assert {a.caso_id for a in avisos} == {caso.id}


def test_no_escala_dos_veces(db):
    caso = _caso_critico(db)
    caso.fecha_apertura = datetime(2026, 11, 9, 8, 0)
    db.commit()
    revisar_casos_criticos(db, hoy=date(2026, 11, 13))
    segunda = revisar_casos_criticos(db, hoy=date(2026, 11, 20))
    assert segunda["escalados"] == 0
