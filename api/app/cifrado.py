"""Cifrado en reposo de las claves de API de los proveedores de IA.

Las claves que introduce el Administrador nunca se guardan en claro: se cifran con una clave
simétrica (Fernet) tomada de `CLAVE_CIFRADO_IA`, que vive en el entorno y no en el
repositorio. Si la variable falta, `cifrar`/`descifrar` fallan con un mensaje
claro: es un error de configuración, no algo que degradar en silencio.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CifradoNoConfigurado(RuntimeError):
    """Falta `CLAVE_CIFRADO_IA`: no se puede cifrar ni descifrar."""


def _fernet() -> Fernet:
    clave = get_settings().clave_cifrado_ia
    if not clave:
        raise CifradoNoConfigurado(
            "Falta CLAVE_CIFRADO_IA: configúrala para guardar o usar claves de IA."
        )
    return Fernet(clave.encode())


def cifrar(texto: str) -> str:
    """Cifra un texto plano y devuelve el token (str) que se persiste."""
    return _fernet().encrypt(texto.encode()).decode()


def descifrar(token: str) -> str:
    """Descifra un token previamente producido por `cifrar`."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # clave rotada o dato corrupto
        raise CifradoNoConfigurado(
            "No se pudo descifrar la clave de IA (¿cambió CLAVE_CIFRADO_IA?)."
        ) from exc
