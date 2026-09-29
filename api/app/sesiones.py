"""Ciclo de vida del refresh token: emisión, rotación y revocación.

La autorización sigue viviendo en `deps.requiere_nivel` (sobre el access token).
Este módulo solo gestiona la sesión de larga duración: emite refresh tokens
opacos, los rota en cada uso y revoca la familia ante `logout` o reutilización.

Se decodifica en errores uniformes (`SesionInvalida`): el router responde 401
sin distinguir "no existe" de "reutilizado" de "expirado", para no filtrar por
qué falló una renovación.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AdminUser, RefreshToken
from app.security import generar_refresh_token, hash_refresh


class SesionInvalida(Exception):
    """El refresh token no es válido (inexistente, revocado, reutilizado o expirado)."""


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """Normaliza a UTC consciente: SQLite devuelve datetimes naive."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _nuevo_token(db: Session, admin_id: int, familia: str) -> str:
    """Crea (sin confirmar) un refresh token en una familia y devuelve el valor en claro."""
    token = generar_refresh_token()
    dias = get_settings().refresh_expire_days
    db.add(
        RefreshToken(
            admin_id=admin_id,
            familia=familia,
            token_hash=hash_refresh(token),
            expira=_ahora() + timedelta(days=dias),
        )
    )
    return token


def emitir_sesion(db: Session, admin: AdminUser) -> str:
    """Abre una sesión nueva (una familia nueva) y devuelve el refresh token opaco."""
    token = _nuevo_token(db, admin.id, uuid.uuid4().hex)
    db.commit()
    return token


def _revocar_familia(db: Session, familia: str) -> None:
    db.query(RefreshToken).filter(RefreshToken.familia == familia).update(
        {RefreshToken.revocado: True}
    )


def rotar_sesion(db: Session, refresh_token: str, portal_id: str) -> tuple[AdminUser, str]:
    """Consume el refresh token y emite uno nuevo en su familia.

    Devuelve `(admin, nuevo_refresh_token)`. Ante cualquier problema lanza
    `SesionInvalida`. Si el token ya se había usado, es reutilización: se revoca
    la familia entera (el atacante y el legítimo pierden la sesión).

    `portal_id` es el portal del host desde el que llega la renovación: el refresh
    solo rota dentro de su propio portal. Un token presentado en otro host se rechaza
    **sin quemarlo** (es una petición mal enrutada, no necesariamente un robo), así que
    la sesión legítima sigue viva en su portal.
    """
    fila = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh(refresh_token)).first()
    if fila is None or fila.revocado:
        raise SesionInvalida

    if fila.usado:
        # Replay de un token ya rotado: se asume robo y se corta la cadena.
        _revocar_familia(db, fila.familia)
        db.commit()
        raise SesionInvalida

    if _aware(fila.expira) < _ahora():
        raise SesionInvalida

    admin = db.get(AdminUser, fila.admin_id)
    if admin is None or not admin.activo:
        raise SesionInvalida

    # El refresh no cruza de portal: pertenece al portal de su administrador. No se
    # marca `usado` antes de esta comprobación, para no invalidar la sesión legítima
    # por una renovación que llegó al host equivocado. `str(...)`: `admin.portal_id`
    # es un `uuid.UUID` (columna `Uuid`); `portal_id` llega como `str` desde el router.
    if str(admin.portal_id) != portal_id:
        raise SesionInvalida

    fila.usado = True
    nuevo = _nuevo_token(db, admin.id, fila.familia)
    db.commit()
    return admin, nuevo


def revocar_sesion(db: Session, refresh_token: str) -> None:
    """Revoca la familia del token (logout). Idempotente: un token desconocido no falla."""
    fila = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh(refresh_token)).first()
    if fila is not None:
        _revocar_familia(db, fila.familia)
        db.commit()
