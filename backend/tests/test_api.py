"""Pruebas de la API: autenticación, permisos por rol y flujos completos."""
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.config import CORTE_VIGENTE
from app.models import Matricula, Usuario
from app.services.riesgo import evaluar_y_atender

from .conftest import CLAVE, estudiante_por_correo, matricula_de, token


# ------------------------------ Autenticación ------------------------------
def test_login_correcto_devuelve_token(client):
    r = client.post("/api/auth/login", data={"username": "admin@u.edu.co", "password": CLAVE})
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer"
    assert cuerpo["expira_en_minutos"] == 30         # RQNF-04
    assert cuerpo["usuario"]["rol"] == "ADMINISTRADOR"


def test_login_con_clave_incorrecta(client):
    r = client.post("/api/auth/login", data={"username": "admin@u.edu.co", "password": "mala"})
    assert r.status_code == 401


def test_endpoint_protegido_sin_token(client):
    assert client.get("/api/estudiantes").status_code == 401


def test_clave_no_se_guarda_en_claro(db):
    usuario = db.scalar(select(Usuario).where(Usuario.correo == "admin@u.edu.co"))
    assert CLAVE not in usuario.password_hash
    assert usuario.password_hash.startswith("$2b$")   # bcrypt


# ------------------------------ Permisos por rol ------------------------------
def test_docente_no_crea_estudiantes(client):
    r = client.post("/api/estudiantes", headers=token(client, "docente@u.edu.co"), json={
        "documento": "90001", "nombre": "Nuevo Estudiante", "correo": "nuevo@u.edu.co",
        "password": "claveclave", "programa_id": 1, "semestre": 1})
    assert r.status_code == 403


def test_admin_crea_estudiante(client):
    r = client.post("/api/estudiantes", headers=token(client, "admin@u.edu.co"), json={
        "documento": "90001", "nombre": "Nuevo Estudiante", "correo": "nuevo@u.edu.co",
        "password": "claveclave", "programa_id": 1, "semestre": 1,
        "promedio_acumulado": 3.8})
    assert r.status_code == 201
    assert r.json()["nombre"] == "Nuevo Estudiante"


def test_documento_duplicado_devuelve_conflicto(client):
    datos = {"documento": "80002", "nombre": "Alguien", "correo": "alguien@u.edu.co",
             "password": "claveclave", "programa_id": 1, "semestre": 1}
    cabeceras = token(client, "admin@u.edu.co")
    assert client.post("/api/estudiantes", headers=cabeceras, json=datos).status_code == 201
    datos["correo"] = "otro@distinto.edu.co"
    assert client.post("/api/estudiantes", headers=cabeceras, json=datos).status_code == 409


# ------------------------------ Captura de desempeño ------------------------------
def test_docente_no_califica_asignatura_ajena(client, db):
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    matricula = matricula_de(db, est)
    r = client.post("/api/desempeno/notas", headers=token(client, "otro@u.edu.co"),
                    json={"matricula_id": matricula.id, "corte": CORTE_VIGENTE, "valor": 3.0})
    assert r.status_code == 403
    assert "no dictas" in r.json()["detail"]


def test_nota_fuera_de_rango_se_rechaza(client, db):
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    matricula = matricula_de(db, est)
    r = client.post("/api/desempeno/notas", headers=token(client, "docente@u.edu.co"),
                    json={"matricula_id": matricula.id, "corte": CORTE_VIGENTE, "valor": 5.5})
    assert r.status_code == 422


def test_inasistencia_futura_se_rechaza(client, db):
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    matricula = matricula_de(db, est)
    manana = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/api/desempeno/inasistencias", headers=token(client, "docente@u.edu.co"),
                    json={"matricula_id": matricula.id, "fecha_sesion": manana})
    assert r.status_code == 422
    assert "futuras" in r.json()["detail"]


def test_nota_mala_dispara_alerta_y_abre_caso(client, db):
    """RQF-03 + RN-03 + RQF-07 de punta a punta."""
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    matricula = matricula_de(db, est)
    r = client.post("/api/desempeno/notas", headers=token(client, "docente@u.edu.co"),
                    json={"matricula_id": matricula.id, "corte": CORTE_VIGENTE, "valor": 0.5})
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["nivel"] in ("ALTO", "CRITICO")
    assert cuerpo["alerta_generada"] is True
    assert cuerpo["caso_nuevo"] is True
    assert cuerpo["caso_id"] is not None


def test_nota_buena_no_abre_caso(client, db):
    est = estudiante_por_correo(db, "sano@u.edu.co")
    matricula = matricula_de(db, est)
    r = client.post("/api/desempeno/notas", headers=token(client, "docente@u.edu.co"),
                    json={"matricula_id": matricula.id, "corte": CORTE_VIGENTE, "valor": 4.5})
    assert r.status_code == 201
    assert r.json()["alerta_generada"] is False
    assert r.json()["caso_id"] is None


# ------------------------------ Casos e intervenciones ------------------------------
def _caso(client, db):
    est = estudiante_por_correo(db, "riesgo@u.edu.co")
    return evaluar_y_atender(db, est)["caso"]


def test_consejero_ajeno_no_ve_el_caso(client, db):
    caso = _caso(client, db)
    r = client.get(f"/api/casos/{caso.id}", headers=token(client, "consejero2@u.edu.co"))
    assert r.status_code == 403


def test_intervencion_pasa_el_caso_a_seguimiento(client, db):
    """RQF-09: la primera intervención mueve el estado."""
    caso = _caso(client, db)
    r = client.post(f"/api/casos/{caso.id}/intervenciones",
                    headers=token(client, "consejero1@u.edu.co"),
                    json={"tipo": "ENTREVISTA",
                          "descripcion": "Primera entrevista de acompañamiento con la estudiante.",
                          "compromisos": "Asistir a todas las clases del corte."})
    assert r.status_code == 201
    detalle = client.get(f"/api/casos/{caso.id}",
                         headers=token(client, "consejero1@u.edu.co")).json()
    assert detalle["estado"] == "EN_SEGUIMIENTO"
    assert detalle["intervenciones"] == 1


def test_cita_en_el_pasado_se_rechaza(client, db):
    caso = _caso(client, db)
    ayer = (datetime.now() - timedelta(days=1)).isoformat()
    r = client.post(f"/api/casos/{caso.id}/intervenciones",
                    headers=token(client, "consejero1@u.edu.co"),
                    json={"tipo": "TUTORIA", "descripcion": "Sesión de tutoría programada",
                          "fecha_cita": ayer})
    assert r.status_code == 422
    assert "fecha pasada" in r.json()["detail"]


def test_flujo_completo_por_api(client, db):
    """Del caso abierto al cierre, pasando por derivación a bienestar."""
    caso = _caso(client, db)
    consejero = token(client, "consejero1@u.edu.co")
    coord = token(client, "coord@u.edu.co")

    client.post(f"/api/casos/{caso.id}/intervenciones", headers=consejero,
                json={"tipo": "ENTREVISTA", "descripcion": "Entrevista inicial con la estudiante.",
                      "compromisos": "Asistir a clases"})
    r = client.post(f"/api/casos/{caso.id}/derivaciones", headers=consejero,
                    json={"tipo_apoyo": "FINANCIERO", "observacion": "Requiere apoyo de transporte"})
    assert r.status_code == 201
    derivacion_id = r.json()["id"]

    client.post(f"/api/casos/{caso.id}/estado", headers=consejero,
                json={"estado": "EN_EVALUACION"})
    bloqueado = client.post(f"/api/casos/{caso.id}/cerrar", headers=coord,
                            json={"resultado": "SUPERADO"})
    assert bloqueado.status_code == 422          # RQF-11: derivación abierta

    atendida = client.post(f"/api/derivaciones/{derivacion_id}/atender",
                           headers=token(client, "bienestar@u.edu.co"),
                           json={"estado": "ATENDIDA", "observacion": "Subsidio aprobado"})
    assert atendida.status_code == 200

    cerrado = client.post(f"/api/casos/{caso.id}/cerrar", headers=coord,
                          json={"resultado": "SUPERADO"})
    assert cerrado.status_code == 200
    assert cerrado.json()["estado"] == "CERRADO"
    assert cerrado.json()["indice_cierre"] is not None


# ------------------------------ Confidencialidad ------------------------------
def test_estudiante_no_ve_notas_de_intervencion(client, db):
    """RQNF-03: el portal entrega compromisos, nunca la descripción."""
    caso = _caso(client, db)
    client.post(f"/api/casos/{caso.id}/intervenciones", headers=token(client, "consejero1@u.edu.co"),
                json={"tipo": "ENTREVISTA",
                      "descripcion": "INFORMACION SENSIBLE QUE NO DEBE SALIR",
                      "compromisos": "Asistir a todas las clases"})
    r = client.get("/api/portal/mi-estado", headers=token(client, "riesgo@u.edu.co"))
    assert r.status_code == 200
    assert "INFORMACION SENSIBLE" not in r.text
    assert r.json()["compromisos"][0]["texto"] == "Asistir a todas las clases"
    assert r.json()["caso_estado"] == "EN_SEGUIMIENTO"


def test_estudiante_no_lista_intervenciones(client, db):
    caso = _caso(client, db)
    r = client.get(f"/api/casos/{caso.id}/intervenciones",
                   headers=token(client, "riesgo@u.edu.co"))
    assert r.status_code == 403


def test_lectura_de_intervenciones_queda_en_bitacora(client, db):
    caso = _caso(client, db)
    consejero = token(client, "consejero1@u.edu.co")
    client.post(f"/api/casos/{caso.id}/intervenciones", headers=consejero,
                json={"tipo": "LLAMADA", "descripcion": "Llamada de seguimiento al estudiante."})
    client.get(f"/api/casos/{caso.id}/intervenciones", headers=consejero)
    r = client.get("/api/admin/bitacora", headers=token(client, "coord@u.edu.co"))
    assert r.status_code == 200
    recursos = {f["recurso"] for f in r.json()}
    assert "INTERVENCION" in recursos


# ------------------------------ Reportes ------------------------------
def test_reporte_general(client, db):
    _caso(client, db)
    r = client.get("/api/reportes/general", headers=token(client, "coord@u.edu.co"))
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["casos_activos"] >= 1
    assert sum(d["cantidad"] for d in cuerpo["distribucion"]) == cuerpo["estudiantes_evaluados"]
    assert 0 <= cuerpo["tasa_retencion_global"] <= 100


def test_docente_no_ve_reportes(client):
    r = client.get("/api/reportes/general", headers=token(client, "docente@u.edu.co"))
    assert r.status_code == 403


def test_salud(client):
    assert client.get("/api/salud").json()["estado"] == "ok"
