"""Autenticación del administrador: login (JWT) y logout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import admin_actual, portal_actual
from app.models import AdminUser, Portal
from app.schemas import LoginIn, LogoutIn, MeOut, RefreshIn, TokenOut
from app.security import crear_token, hash_password, verify_password
from app.sesiones import SesionInvalida, emitir_sesion, revocar_sesion, rotar_sesion

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash de descarte para igualar el tiempo de respuesta cuando el correo no existe.
# Sin esto, argon2 solo se ejecuta con correos válidos y la diferencia de latencia
# (decenas de milisegundos frente a menos de uno) delata qué correos son de
# administrador, anulando el mensaje genérico de más abajo.
_HASH_DESCARTE = hash_password("comparacion-de-descarte")


@router.post("/login", response_model=TokenOut)
def login(
    datos: LoginIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> TokenOut:
    # La sesión se emite dentro del portal del host: se busca el usuario por
    # `(portal_id, email)`. Una credencial de otro portal no inicia sesión aquí.
    admin = (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == portal.id, AdminUser.email == datos.email)
        .first()
    )
    hash_a_verificar = admin.password_hash if admin is not None else _HASH_DESCARTE
    correcta = verify_password(hash_a_verificar, datos.password)

    # Mensaje genérico: no revela si falló el correo o la contraseña. Un usuario
    # desactivado se rechaza igual (y con el mismo mensaje): sin esto obtendría un
    # token que `admin_actual` rechazaría en la siguiente petición, un bucle
    # confuso de "entro pero todo da 401". El argon2 ya se ejecutó arriba, así que
    # comprobar `activo` aquí no añade una diferencia de tiempo aprovechable.
    if admin is None or not correcta or not admin.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    return TokenOut(
        access_token=crear_token(admin.email, str(admin.portal_id)),
        refresh_token=emitir_sesion(db, admin),
    )


@router.post("/refresh", response_model=TokenOut)
def refresh(
    datos: RefreshIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> TokenOut:
    # El BFF llama aquí con el refresh token de la cookie cuando el access expira.
    # Rota el refresh (uno de un solo uso) dentro del portal del host y emite un access
    # nuevo. Un token inválido, expirado, reutilizado o de otro portal responde 401
    # uniforme (no revela cuál de esas causas falló ni la existencia de otro portal).
    try:
        admin, nuevo_refresh = rotar_sesion(db, datos.refresh_token, str(portal.id))
    except SesionInvalida:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")
    return TokenOut(
        access_token=crear_token(admin.email, str(admin.portal_id)),
        refresh_token=nuevo_refresh,
    )


@router.post("/logout")
def logout(datos: LogoutIn | None = None, db: Session = Depends(get_db)) -> dict:
    # No exige access token y el cuerpo es opcional: el logout siempre debe poder
    # cerrar la sesión. Si llega el refresh token, se revoca su familia entera en
    # el servidor; el BFF borra las cookies en cualquier caso.
    if datos is not None and datos.refresh_token:
        revocar_sesion(db, datos.refresh_token)
    return {"detail": "Sesión cerrada"}


@router.get("/me", response_model=MeOut)
def yo(admin: AdminUser = Depends(admin_actual)) -> MeOut:
    # El frontend lo consulta para ajustar la interfaz al nivel de la sesión
    # (ocultar los controles de Administrador). La autoridad sigue siendo el backend.
    return MeOut(email=admin.email, nivel=admin.nivel)
