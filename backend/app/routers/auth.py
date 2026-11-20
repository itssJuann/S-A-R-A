"""Autenticación (RQNF-04)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import MINUTOS_EXPIRACION_SESION
from ..database import get_db
from ..models import Usuario
from ..schemas import Token, UsuarioOut
from ..security import crear_token, usuario_actual, verificar_password

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/login", response_model=Token, summary="Iniciar sesión")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """`username` es el correo institucional."""
    usuario = db.scalar(select(Usuario).where(Usuario.correo == form.username))
    if not usuario or not verificar_password(form.password, usuario.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    if not usuario.activo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El usuario está inactivo")
    return {
        "access_token": crear_token(usuario),
        "token_type": "bearer",
        "expira_en_minutos": MINUTOS_EXPIRACION_SESION,
        "usuario": _salida(usuario),
    }


@router.get("/me", response_model=UsuarioOut, summary="Usuario de la sesión actual")
def me(usuario: Usuario = Depends(usuario_actual)):
    return _salida(usuario)


def _salida(u: Usuario) -> dict:
    return {"id": u.id, "documento": u.documento, "nombre": u.nombre, "correo": u.correo,
            "rol": u.rol.nombre, "programa_id": u.programa_id, "activo": u.activo}
