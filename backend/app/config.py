"""Configuración de la aplicación.

Todos los valores se pueden sobrescribir con variables de entorno, de modo que
el mismo código corre en desarrollo (SQLite) y en producción (PostgreSQL).
"""
import os

# Base de datos. Por defecto SQLite para que el proyecto arranque sin instalar nada.
# Para PostgreSQL:  postgresql+psycopg://usuario:clave@localhost:5432/sara
DATABASE_URL = os.getenv("SARA_DATABASE_URL", "sqlite:///./sara.db")

# Seguridad (RQNF-04)
SECRET_KEY = os.getenv("SARA_SECRET_KEY", "cambia-esta-clave-en-produccion")
ALGORITHM = "HS256"
MINUTOS_EXPIRACION_SESION = int(os.getenv("SARA_SESSION_MINUTES", "30"))

# Reglas de negocio configurables
MAX_CASOS_ACTIVOS_POR_CONSEJERO = int(os.getenv("SARA_MAX_CASOS", "20"))   # RN-04
DIAS_HABILES_ESCALAMIENTO = int(os.getenv("SARA_DIAS_ESCALAMIENTO", "3"))  # RN-06
# El semestre académico se divide en 4 cortes de calificación.
CORTES_POR_SEMESTRE = int(os.getenv("SARA_CORTES", "4"))                    # RN-07
PERIODO_VIGENTE = os.getenv("SARA_PERIODO", "2026-2")
CORTE_VIGENTE = int(os.getenv("SARA_CORTE_VIGENTE", str(CORTES_POR_SEMESTRE)))

# Umbrales de nivel de riesgo (RN-02)
UMBRAL_MEDIO = 40
UMBRAL_ALTO = 65
UMBRAL_CRITICO = 85

# CORS: orígenes del frontend en desarrollo
ORIGENES_PERMITIDOS = os.getenv(
    "SARA_CORS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
