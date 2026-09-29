"""Detección del tipo real de imagen por *magic bytes*, para la subida del logotipo.

Se admiten **PNG, ICO y JPEG**. El tipo se decide por el contenido, nunca por la
extensión ni por el `Content-Type` que declara el cliente (ambos falsificables). Se
descarta SVG a propósito: al no aceptar vectores no hay superficie de SVG-con-script.
"""

from __future__ import annotations

# Tamaño máximo del logo. Es un singleton en la base (no crece con el contenido); el
# límite corta subidas desmesuradas.
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB

# Firmas de archivo (primeros bytes).
_PNG = b"\x89PNG\r\n\x1a\n"
# ICO: reservado=0x0000, tipo=0x0001 (0x0002 sería CUR, que no admitimos).
_ICO = b"\x00\x00\x01\x00"
# JPEG: SOI (Start Of Image). Cubre JFIF/Exif y demás variantes, que comparten prefijo.
_JPEG = b"\xff\xd8\xff"

MIME_PNG = "image/png"
MIME_ICO = "image/x-icon"
MIME_JPEG = "image/jpeg"


def detectar_mime_logo(datos: bytes) -> str | None:
    """Devuelve el MIME real (`image/png`, `image/x-icon` o `image/jpeg`), o `None`."""
    if datos.startswith(_PNG):
        return MIME_PNG
    if datos.startswith(_ICO):
        return MIME_ICO
    if datos.startswith(_JPEG):
        return MIME_JPEG
    return None
