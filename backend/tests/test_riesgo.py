"""Pruebas del motor de riesgo (RN-01, RN-02, RQF-02, RQF-05)."""
import pytest
from sqlalchemy import select

from app.config import CORTE_VIGENTE
from app.models import FactorRiesgo, NivelRiesgo, Nota
from app.services.riesgo import ErrorModelo, calcular_indice, clasificar, evaluar

from .conftest import estudiante_por_correo, matricula_de, token


def test_clasificacion_por_umbrales():
    """RN-02: los cuatro niveles y sus fronteras exactas."""
    assert clasificar(0) is NivelRiesgo.BAJO
    assert clasificar(39.99) is NivelRiesgo.BAJO
    assert clasificar(40) is NivelRiesgo.MEDIO
    assert clasificar(64.99) is NivelRiesgo.MEDIO
    assert clasificar(65) is NivelRiesgo.ALTO
    assert clasificar(84.99) is NivelRiesgo.ALTO
    assert clasificar(85) is NivelRiesgo.CRITICO
    assert clasificar(100) is NivelRiesgo.CRITICO


def test_indice_es_suma_ponderada(db):
    """RN-01: el índice es exactamente la suma de los aportes de cada factor."""
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    indice, nivel, detalle, version = calcular_indice(db, est)
    assert len(detalle) == 5
    assert indice == pytest.approx(round(sum(d.aporte for d in detalle), 2))
    assert 0 <= indice <= 100
    for d in detalle:
        assert 0 <= d.valor <= 100
        assert d.aporte == pytest.approx(round(d.valor * d.peso / 100, 2))
        assert d.evidencia      # todo factor explica de dónde salió su valor


def test_estudiante_sin_riesgo_queda_bajo(db):
    est = estudiante_por_correo(db, "sano@u.edu.co")
    indice, nivel, _, _ = calcular_indice(db, est)
    assert nivel is NivelRiesgo.BAJO
    assert indice < 40


def test_nota_baja_sube_el_indice(db):
    """Registrar una nota mala debe aumentar el índice del estudiante."""
    est = estudiante_por_correo(db, "sano@u.edu.co")
    antes, _, _, _ = calcular_indice(db, est)
    matricula = matricula_de(db, est)
    db.add(Nota(matricula_id=matricula.id, corte=CORTE_VIGENTE, valor=0.5, registrada_por=1))
    db.commit()
    despues, _, _, _ = calcular_indice(db, est)
    assert despues > antes


def test_pesos_deben_sumar_cien(db):
    """RQF-02: con pesos que no suman 100 el motor se niega a calcular."""
    factor = db.scalar(select(FactorRiesgo).where(FactorRiesgo.codigo == "HISTORICO"))
    factor.peso = 25          # ahora suman 115
    db.commit()
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    with pytest.raises(ErrorModelo, match="deben sumar 100"):
        calcular_indice(db, est)


def test_evaluacion_guarda_version_y_detalle(db):
    """Cada evaluación es reproducible: guarda versión del modelo y aportes."""
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    evaluacion = evaluar(db, est)
    assert evaluacion.version_modelo == 1
    assert len(evaluacion.detalle_factores) == 5
    assert {d["codigo"] for d in evaluacion.detalle_factores} == {
        "RENDIMIENTO", "INASISTENCIA", "REPETIDAS", "FINANCIERA", "HISTORICO"}


def test_api_rechaza_configuracion_invalida(client, db):
    """RQF-02 por API: pesos que no suman 100 se rechazan sin aplicar cambios."""
    cabeceras = token(client, "admin@u.edu.co")
    r = client.put("/api/admin/factores", headers=cabeceras, json={"factores": [
        {"codigo": "RENDIMIENTO", "peso": 50}, {"codigo": "INASISTENCIA", "peso": 30},
    ]})
    assert r.status_code == 422
    assert "100%" in r.json()["detail"]
    vigentes = db.scalars(select(FactorRiesgo).where(FactorRiesgo.vigente.is_(True))).all()
    assert len(vigentes) == 5          # no se tocó nada


def test_api_acepta_configuracion_valida_y_sube_version(client, db):
    cabeceras = token(client, "admin@u.edu.co")
    r = client.put("/api/admin/factores", headers=cabeceras, json={"factores": [
        {"codigo": "RENDIMIENTO", "peso": 40}, {"codigo": "INASISTENCIA", "peso": 30},
        {"codigo": "REPETIDAS", "peso": 15}, {"codigo": "FINANCIERA", "peso": 10},
        {"codigo": "HISTORICO", "peso": 5},
    ]})
    assert r.status_code == 200
    assert all(f["version_modelo"] == 2 for f in r.json())
    assert sum(f["peso"] for f in r.json()) == 100
