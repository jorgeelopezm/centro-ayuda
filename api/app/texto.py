"""Utilidades de texto compartidas. `normalizar_slug` reproduce la misma regla
que el frontend (`app/src/data/slug.ts`) para que id y slug se normalicen igual
en cliente y servidor: el cliente adelanta la vista, el servidor es la autoridad.
"""

from __future__ import annotations

import re
import unicodedata


def normalizar_slug(texto: str) -> str:
    """Minúsculas, sin acentos, espacios/signos a guiones, sin guiones repetidos.

    Ej.: "Cómo cambiar tu contraseña" -> "como-cambiar-tu-contrasena".
    """
    # Descompone acentos (á -> a + ´) y descarta los diacríticos.
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    minusculas = sin_acentos.lower()
    # Cualquier cosa que no sea letra/dígito ASCII pasa a guion.
    con_guiones = re.sub(r"[^a-z0-9]+", "-", minusculas)
    return con_guiones.strip("-")
