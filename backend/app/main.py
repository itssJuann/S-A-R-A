"""Punto de entrada de la API de SARA."""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import ORIGENES_PERMITIDOS
from .database import Base, engine
from .routers import (
    academico, admin, auth, casos, derivaciones, desempeno, intervenciones,
    notificaciones, portal, reportes, riesgo,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DESCRIPCION = """
API del **Sistema de Alerta Temprana y Retención Académica (SARA)**.

Calcula un índice de riesgo de deserción por estudiante a partir de factores
ponderados y configurables. Cuando el índice llega a nivel **Alto** o **Crítico**,
abre un caso de acompañamiento, lo asigna al consejero con menos carga y hace
seguimiento hasta cerrarlo con un resultado verificable.

Las reglas de negocio están identificadas como `RN-xx` y los requerimientos
como `RQF-xx` / `RQNF-xx`, igual que en el documento de la Entrega 1.
"""

app = FastAPI(
    title="SARA — Sistema de Alerta Temprana y Retención Académica",
    description=DESCRIPCION,
    version="1.0.0",
    contact={"name": "Equipo SARA — Diseño de Software I"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for modulo in (auth, admin, academico, desempeno, riesgo, casos,
               intervenciones, derivaciones, notificaciones, portal, reportes):
    app.include_router(modulo.router)


@app.on_event("startup")
def iniciar():
    Base.metadata.create_all(bind=engine)
    # En un servidor recién desplegado la base está vacía: con SARA_SEMBRAR=1 se
    # cargan los datos de demostración en el primer arranque. El seed no hace
    # nada si ya hay usuarios, así que es seguro dejar la variable puesta.
    if os.getenv("SARA_SEMBRAR", "0") == "1":
        from .seed import sembrar
        try:
            sembrar()
        except Exception:
            logging.getLogger("sara").exception("No se pudo sembrar la base")
    from .scheduler import iniciar_planificador
    iniciar_planificador()


@app.get("/api/salud", tags=["Sistema"], summary="Comprobar que la API responde")
def salud():
    return {"estado": "ok", "servicio": "SARA", "version": "1.0.0"}


@app.get("/api/configuracion", tags=["Sistema"],
         summary="Periodo y cortes vigentes del semestre")
def configuracion():
    """La interfaz lee de aquí el periodo y los cortes, en vez de fijarlos a mano."""
    from .config import (
        CORTE_VIGENTE, CORTES_POR_SEMESTRE, PERIODO_VIGENTE,
        UMBRAL_ALTO, UMBRAL_CRITICO, UMBRAL_MEDIO,
    )
    return {
        "periodo": PERIODO_VIGENTE,
        "cortes": list(range(1, CORTES_POR_SEMESTRE + 1)),
        "corte_vigente": CORTE_VIGENTE,
        "umbrales": {"medio": UMBRAL_MEDIO, "alto": UMBRAL_ALTO, "critico": UMBRAL_CRITICO},
    }


# ---------------------------------------------------------------------------
# Servir el frontend compilado (frontend/dist) desde el mismo servidor.
# Así la aplicación completa corre con un solo comando: uvicorn app.main:app
# Si la carpeta dist no existe, la API sigue funcionando igual.
# ---------------------------------------------------------------------------
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{ruta_spa:path}", include_in_schema=False)
    def servir_spa(ruta_spa: str):
        """Devuelve index.html para cualquier ruta del enrutador de React."""
        archivo = DIST / ruta_spa
        if ruta_spa and archivo.is_file():
            return FileResponse(archivo)
        return FileResponse(DIST / "index.html")
