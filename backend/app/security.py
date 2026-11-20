"""Autenticación y autorización (RQNF-03, RQNF-04).

Contraseñas con bcrypt, sesión por JWT que expira a los 30 minutos de inactividad.
"""
from datetime import datetime, timedelta, timezone

import os

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import ALGORITHM, MINUTOS_EXPIRACION_SESION, SECRET_KEY
from .database import get_db
from .models import RolNombre, Usuario

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


RONDAS_BCRYPT = int(os.getenv("SARA_BCRYPT_ROUNDS", "12"))


def hash_password(clave: str) -> str:
    return bcrypt.hashpw(clave.encode("utf-8"), bcrypt.gensalt(RONDAS_BCRYPT)).decode("utf-8")


def verificar_password(clave: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(clave.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        return False


def crear_token(usuario: Usuario) -> str:
    expira = datetime.now(timezone.utc) + timedelta(minutes=MINUTOS_EXPIRACION_SESION)
    payload = {"sub": str(usuario.id), "rol": usuario.rol.nombre.value, "exp": expira}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def usuario_actual(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión inválida o expirada",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        usuario_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise error
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise error
    return usuario


def exige_rol(*roles: RolNombre):
    """Dependencia que restringe un endpoint a ciertos roles."""
    permitidos = set(roles)

    def verificador(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol.nombre not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"El rol {usuario.rol.nombre.value} no tiene permiso para esta operación",
            )
        return usuario

    return verificador
