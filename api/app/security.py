"""Hash de contraseñas (argon2) y emisión/verificación de JWT."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import get_settings

_hasher = PasswordHasher()


@dataclass(frozen=True)
class DatosToken:
    """Identidad que porta el access token: a quién y **en qué portal**.

    El portal viaja en el propio token (no solo el correo) porque el correo es único
    por portal, no globalmente: dos portales pueden tener cada uno un `admin@x.com`.
    Sin el portal en el token, uno emitido en el portal A serviría para autenticarse
    como el homónimo del portal B. `admin_actual` exige que este `portal_id` coincida
    con el portal del host.
    """

    email: str
    portal_id: str


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def crear_token(subject: str, portal_id: str) -> str:
    # `portal_id` debe llegar ya como `str`: `Portal.id` es un `uuid.UUID` (columna
    # `Uuid`) y `jwt.encode` no lo serializa por sí solo (el llamador hace `str(...)`).
    s = get_settings()
    payload = {
        "sub": subject,
        "portal": portal_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decodificar_token(token: str) -> DatosToken | None:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    portal = payload.get("portal")
    # Ambos deben ser texto: un token sin `portal` (o con un valor no textual) no
    # identifica el portal y no puede autorizarse; se descarta como inválido.
    if not isinstance(sub, str) or not isinstance(portal, str):
        return None
    return DatosToken(email=sub, portal_id=portal)


# --- Refresh tokens opacos -------------------------------------------------
#
# El refresh token NO es un JWT: es un valor aleatorio opaco. Se entrega en claro
# al cliente (cookie httpOnly) pero en la base solo se guarda su hash SHA-256, de
# modo que una fuga de la base no permite reutilizar sesiones. Al ser de un solo
# uso (rota en cada renovación), no necesita el coste de argon2.


def generar_refresh_token() -> str:
    """Devuelve un refresh token opaco de 256 bits, seguro para URL/cookie."""
    return secrets.token_urlsafe(32)


def hash_refresh(token: str) -> str:
    """Hash con el que se busca y almacena el refresh token (nunca el valor en claro)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
