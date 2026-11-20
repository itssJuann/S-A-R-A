# SARA — imagen única que sirve la API y el frontend compilado.
# Funciona igual en Render, Railway, Fly.io o cualquier servidor con Docker.

# ---------------------------------------------------------------- 1. Frontend
FROM node:20-slim AS frontend

WORKDIR /app/frontend
# Primero las dependencias: así Docker reutiliza esta capa mientras no cambien.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- 2. Backend
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
# El backend sirve frontend/dist, así que la compilación va en esa misma ruta.
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Usuario sin privilegios: el contenedor no necesita ser root para servir HTTP.
RUN useradd --create-home sara && chown -R sara:sara /app
USER sara

WORKDIR /app/backend
EXPOSE 8000

# El proveedor inyecta PORT; en local se usa 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
