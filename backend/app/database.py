"""Conexión a la base de datos y sesión de SQLAlchemy."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL


def normalizar(url: str) -> str:
    """Adapta la URL que entregan los servicios gestionados al driver que usamos.

    Render, Railway y Heroku publican la variable como `postgres://...` o
    `postgresql://...`, que SQLAlchemy intentaría abrir con psycopg2. Aquí se
    reescribe al driver psycopg 3, que es el que instala requirements.txt.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


URL = normalizar(DATABASE_URL)
es_sqlite = URL.startswith("sqlite")

# check_same_thread solo aplica a SQLite; en PostgreSQL se ignora.
connect_args = {"check_same_thread": False} if es_sqlite else {}
engine = create_engine(
    URL, connect_args=connect_args, future=True,
    # Los Postgres gestionados cierran conexiones ociosas: comprobarlas antes de
    # usarlas evita el típico error "server closed the connection unexpectedly".
    pool_pre_ping=not es_sqlite,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependencia de FastAPI: abre una sesión por petición y la cierra siempre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
