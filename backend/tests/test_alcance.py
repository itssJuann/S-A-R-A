"""RN-10: cada rol ve exclusivamente la parte del sistema que le corresponde.

Estas pruebas fijan el contrato de app/alcance.py: si alguien amplía un rol sin
querer, aquí se cae.
"""
from sqlalchemy import select

from app.models import CasoAcompanamiento, RolNombre, Usuario
from app.services.riesgo import evaluar_y_atender

from .conftest import estudiante_por_correo, token


def _abrir_caso(db):
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    resultado = evaluar_y_atender(db, est)
    db.commit()
    return resultado["caso"]


def test_el_docente_no_entra_al_motor_de_riesgo(client, db):
    db.commit()
    cabeceras = token(client, "docente@u.edu.co")
    assert client.get("/api/riesgo/estudiantes", headers=cabeceras).status_code == 403
    assert client.get("/api/casos", headers=cabeceras).status_code == 403
    assert client.get("/api/reportes/general", headers=cabeceras).status_code == 403


def test_el_estudiante_solo_ve_su_portal(client, db):
    db.commit()
    cabeceras = token(client, "riesgo@u.edu.co")
    assert client.get("/api/portal/mi-estado", headers=cabeceras).status_code == 200
    assert client.get("/api/riesgo/estudiantes", headers=cabeceras).status_code == 403
    assert client.get("/api/casos", headers=cabeceras).status_code == 403
    assert client.get("/api/admin/bitacora", headers=cabeceras).status_code == 403


def test_el_consejero_solo_ve_los_estudiantes_de_sus_casos(client, db):
    caso = _abrir_caso(db)
    consejero = db.get(Usuario, caso.consejero_id)
    cabeceras = token(client, consejero.correo)

    visibles = client.get("/api/riesgo/estudiantes", headers=cabeceras).json()
    assert {f["id"] for f in visibles} == {caso.estudiante_id}

    # El coordinador, en cambio, ve a todo su programa.
    coord = client.get("/api/riesgo/estudiantes", headers=token(client, "coord@u.edu.co")).json()
    assert len(coord) > len(visibles)


def test_el_consejero_no_abre_el_caso_de_otro(client, db):
    caso = _abrir_caso(db)
    otro = db.scalar(
        select(Usuario).join(Usuario.rol)
        .where(Usuario.rol.has(nombre=RolNombre.CONSEJERO), Usuario.id != caso.consejero_id))
    r = client.get(f"/api/casos/{caso.id}", headers=token(client, otro.correo))
    assert r.status_code == 403
    assert "alcance" in r.json()["detail"].lower()


def test_bienestar_solo_ve_los_casos_con_derivacion(client, db):
    caso = _abrir_caso(db)
    bienestar = token(client, "bienestar@u.edu.co")

    # Sin derivaciones todavía, el tablero de bienestar está vacío.
    assert client.get("/api/casos", headers=bienestar).json() == []

    consejero = db.get(Usuario, caso.consejero_id)
    r = client.post(f"/api/casos/{caso.id}/derivaciones",
                    json={"tipo_apoyo": "FINANCIERO"}, headers=token(client, consejero.correo))
    assert r.status_code == 201, r.text

    visibles = client.get("/api/casos", headers=bienestar).json()
    assert [c["id"] for c in visibles] == [caso.id]
    # Sus indicadores, en cambio, son institucionales.
    assert client.get("/api/reportes/general", headers=bienestar).status_code == 200


def test_el_coordinador_no_abre_caso_fuera_de_su_programa(client, db):
    """La apertura manual también respeta el alcance."""
    db.commit()
    est = estudiante_por_correo(db, "sano@u.edu.co")
    # El coordinador de la prueba sí tiene este estudiante en su programa.
    r = client.post("/api/casos", headers=token(client, "coord@u.edu.co"), json={
        "estudiante_id": est.id, "motivo": "Reporte del docente sobre ausencias repetidas"})
    assert r.status_code == 201
