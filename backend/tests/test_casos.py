"""Pruebas de los casos de acompañamiento (RN-03, RN-04, RN-05, RN-08, RN-09)."""
import pytest
from sqlalchemy import select

from app.models import (
    CasoAcompanamiento, Derivacion, EstadoCaso, NivelRiesgo, ResultadoCaso,
    RolNombre, TipoApoyo, Usuario,
)
from app.services import casos as servicio
from app.services.riesgo import evaluar, evaluar_y_atender

from .conftest import estudiante_por_correo, token


def _abrir_caso(db):
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    resultado = evaluar_y_atender(db, est)
    assert resultado["alerta"], "el estudiante de prueba debería quedar en riesgo Alto o Crítico"
    return resultado["caso"]


def test_alerta_abre_y_asigna_caso(db):
    """RN-03 + RQF-08: el caso nace Abierto y queda Asignado automáticamente."""
    caso = _abrir_caso(db)
    assert caso is not None
    assert caso.estado is EstadoCaso.ASIGNADO
    assert caso.consejero_id is not None
    assert caso.nivel_apertura in (NivelRiesgo.ALTO, NivelRiesgo.CRITICO)
    # El historial deja constancia de las dos transiciones.
    motivos = [h.motivo for h in caso.historial]
    assert "APERTURA_AUTOMATICA" in motivos
    assert "ASIGNACION_AUTOMATICA" in motivos


def test_un_solo_caso_abierto_por_estudiante(db):
    """RN-09: una segunda alerta se adjunta al caso vigente."""
    primero = _abrir_caso(db)
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    segundo = evaluar_y_atender(db, est)
    assert segundo["caso_nuevo"] is False
    assert segundo["caso"].id == primero.id
    total = db.scalars(select(CasoAcompanamiento)
                       .where(CasoAcompanamiento.estudiante_id == est.id)).all()
    assert len(total) == 1


def test_asignacion_al_consejero_con_menos_carga(db):
    """RN-04: desempata por carga, no por orden alfabético."""
    uno = db.scalar(select(Usuario).where(Usuario.correo == "consejero1@u.edu.co"))
    dos = db.scalar(select(Usuario).where(Usuario.correo == "consejero2@u.edu.co"))
    programa_id = uno.programa_id
    # Sin casos, gana el de menor id.
    assert servicio.consejero_con_menos_casos(db, programa_id).id == uno.id

    caso = _abrir_caso(db)
    assert caso.consejero_id == uno.id
    # Ahora el primero tiene un caso activo: el siguiente debe ir al segundo.
    assert servicio.consejero_con_menos_casos(db, programa_id).id == dos.id


def test_sin_consejeros_con_cupo_no_asigna(db, monkeypatch):
    """RQF-08: si nadie tiene cupo, el caso queda Abierto y se avisa al coordinador."""
    monkeypatch.setattr(servicio, "MAX_CASOS_ACTIVOS_POR_CONSEJERO", 0)
    caso = _abrir_caso(db)
    assert caso.estado is EstadoCaso.ABIERTO
    assert caso.consejero_id is None


def test_no_se_pueden_saltar_estados(db):
    """RN-05: de Asignado no se salta a En evaluación."""
    caso = _abrir_caso(db)
    with pytest.raises(servicio.ErrorCaso, match="Transición no permitida"):
        servicio.cambiar_estado(db, caso, EstadoCaso.EN_EVALUACION)
    db.rollback()


def test_flujo_completo_de_estados(db):
    caso = _abrir_caso(db)
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO, usuario=coord)
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_EVALUACION, usuario=coord)
    # El coordinador puede devolverlo a seguimiento si no está concluido.
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO, usuario=coord)
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_EVALUACION, usuario=coord)
    servicio.cerrar(db, caso, ResultadoCaso.SUPERADO, coord)
    db.commit()
    assert caso.estado is EstadoCaso.CERRADO
    assert caso.resultado is ResultadoCaso.SUPERADO
    assert caso.indice_cierre is not None      # RN-08: índice recalculado al cierre
    assert caso.fecha_cierre is not None


def test_caso_cerrado_no_admite_mas_transiciones(db):
    caso = _abrir_caso(db)
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO, usuario=coord)
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_EVALUACION, usuario=coord)
    servicio.cerrar(db, caso, ResultadoCaso.PERSISTE, coord)
    with pytest.raises(servicio.ErrorCaso):
        servicio.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO, usuario=coord)
    db.rollback()


def test_no_cierra_con_derivacion_abierta(db):
    """RQF-11: una derivación abierta bloquea el cierre."""
    caso = _abrir_caso(db)
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    db.add(Derivacion(caso_id=caso.id, tipo_apoyo=TipoApoyo.FINANCIERO,
                      solicitada_por=caso.consejero_id))
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO, usuario=coord)
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_EVALUACION, usuario=coord)
    db.commit()
    with pytest.raises(servicio.ErrorCaso, match="derivación"):
        servicio.cerrar(db, caso, ResultadoCaso.SUPERADO, coord)
    db.rollback()


def test_solo_consejero_asignado_o_coordinador_cierran(db):
    """RQF-12: un consejero ajeno no puede cerrar el caso."""
    caso = _abrir_caso(db)
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    ajeno = db.scalar(select(Usuario).where(Usuario.correo == "consejero2@u.edu.co"))
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO, usuario=coord)
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_EVALUACION, usuario=coord)
    db.commit()
    with pytest.raises(servicio.ErrorCaso, match="Solo el consejero asignado"):
        servicio.cerrar(db, caso, ResultadoCaso.SUPERADO, ajeno)
    db.rollback()


def test_api_rechaza_transicion_invalida(client, db):
    caso = _abrir_caso(db)
    cabeceras = token(client, "coord@u.edu.co")
    r = client.post(f"/api/casos/{caso.id}/estado", headers=cabeceras,
                    json={"estado": "EN_EVALUACION"})
    assert r.status_code == 422
    assert "Transición no permitida" in r.json()["detail"]


def test_api_cerrar_exige_endpoint_propio(client, db):
    caso = _abrir_caso(db)
    cabeceras = token(client, "coord@u.edu.co")
    r = client.post(f"/api/casos/{caso.id}/estado", headers=cabeceras,
                    json={"estado": "CERRADO"})
    assert r.status_code == 422
    assert "cerrar" in r.json()["detail"]


# --------------------------------------------------------------------------
# Acciones del coordinador
# --------------------------------------------------------------------------
def test_coordinador_abre_caso_manualmente(db):
    """RQF-08: el coordinador puede abrir un caso que el índice no disparó."""
    est = estudiante_por_correo(db, "sano@u.edu.co")
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    caso = servicio.abrir_manualmente(
        db, est, coord, "Reporte del docente: dejó de asistir tras una situación familiar")
    db.commit()
    assert caso.estado in (EstadoCaso.ABIERTO, EstadoCaso.ASIGNADO)
    motivos = [h.motivo for h in caso.historial]
    assert "APERTURA_MANUAL" in motivos
    # Queda registrado quién lo abrió, no el "Sistema".
    apertura = next(h for h in caso.historial if h.motivo == "APERTURA_MANUAL")
    assert apertura.usuario_id == coord.id


def test_apertura_manual_exige_motivo(db):
    est = estudiante_por_correo(db, "sano@u.edu.co")
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    with pytest.raises(servicio.ErrorCaso):
        servicio.abrir_manualmente(db, est, coord, "corto")


def test_apertura_manual_respeta_un_solo_caso_activo(db):
    """RN-09 también rige para la apertura manual."""
    caso = _abrir_caso(db)
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    with pytest.raises(servicio.ErrorCaso):
        servicio.abrir_manualmente(db, est, coord, "Quiero abrir otro caso en paralelo")
    assert caso.estado is EstadoCaso.ASIGNADO


def test_reabrir_devuelve_el_caso_a_seguimiento(db):
    caso = _abrir_caso(db)
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_SEGUIMIENTO)
    servicio.cambiar_estado(db, caso, EstadoCaso.EN_EVALUACION)
    servicio.cerrar(db, caso, ResultadoCaso.SUPERADO, coord)
    db.commit()
    assert caso.estado is EstadoCaso.CERRADO

    servicio.reabrir(db, caso, coord, "El estudiante volvió a faltar la semana siguiente")
    db.commit()
    assert caso.estado is EstadoCaso.EN_SEGUIMIENTO
    assert caso.resultado is None and caso.fecha_cierre is None
    assert "REAPERTURA" in [h.motivo for h in caso.historial]


def test_no_se_reabre_un_caso_que_no_esta_cerrado(db):
    caso = _abrir_caso(db)
    coord = db.scalar(select(Usuario).where(Usuario.correo == "coord@u.edu.co"))
    with pytest.raises(servicio.ErrorCaso):
        servicio.reabrir(db, caso, coord, "Motivo suficientemente largo para pasar")


def test_api_registra_las_acciones_del_coordinador(client, db):
    """RQNF-03: abrir, cambiar de estado y cerrar quedan en la bitácora."""
    caso = _abrir_caso(db)
    db.commit()
    cabeceras = token(client, "coord@u.edu.co")

    r = client.post(f"/api/casos/{caso.id}/estado",
                    json={"estado": "EN_SEGUIMIENTO"}, headers=cabeceras)
    assert r.status_code == 200

    acciones = r.json()["acciones"]
    assert any(a["accion"] == "CAMBIO_ESTADO" for a in acciones)
    assert any("Asignado → En seguimiento" in (a["detalle"] or "") for a in acciones)

    bitacora = client.get("/api/admin/bitacora", headers=cabeceras).json()
    registradas = {b["accion"] for b in bitacora}
    assert "CAMBIO_ESTADO" in registradas


def test_api_coordinador_abre_caso(client, db):
    est = estudiante_por_correo(db, "sano@u.edu.co")
    db.commit()
    cabeceras = token(client, "coord@u.edu.co")
    r = client.post("/api/casos", headers=cabeceras, json={
        "estudiante_id": est.id,
        "motivo": "La profesora reportó ausencias repetidas sin justificar",
    })
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert any(a["accion"] == "APERTURA" for a in cuerpo["acciones"])


def test_api_consejero_no_puede_abrir_caso(client, db):
    est = estudiante_por_correo(db, "sano@u.edu.co")
    db.commit()
    cabeceras = token(client, "consejero1@u.edu.co")
    r = client.post("/api/casos", headers=cabeceras, json={
        "estudiante_id": est.id, "motivo": "Intento abrir un caso sin ser coordinador"})
    assert r.status_code == 403
