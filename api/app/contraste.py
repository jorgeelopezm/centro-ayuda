"""Contraste WCAG 2.2 y derivación de la escala de acento. Lógica pura y probada.

La autoridad de la validación de paleta vive aquí (servidor): `PUT /api/admin/ajustes/marca`
la usa para **rechazar** cualquier acento/banner que degrade la accesibilidad. El
frontend tiene un espejo puro (`app/src/seguridad/contraste.ts`) solo para adelantar el
aviso; nunca decide.

Fórmulas: luminancia relativa y relación de contraste de WCAG 2.1/2.2. Umbrales AA:
4.5:1 para texto normal y 3:1 para texto grande, componentes de interfaz y el foco.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# Umbrales WCAG 2.2 nivel AA.
AA_NORMAL = 4.5  # texto normal
AA_GRANDE = 3.0  # texto grande, componentes de interfaz y el indicador de foco

# Colores de referencia fijos de la interfaz.
BLANCO = "#ffffff"  # texto sobre botón/banner y superficie/fondo base de la app
FONDO = "#ffffff"   # fondo contra el que se mide el anillo de foco

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ResultadoContraste(NamedTuple):
    """Par de colores que incumple, con el ratio obtenido y el mínimo exigido."""

    par: str
    ratio: float
    minimo: float


def hex_a_rgb(color: str) -> tuple[int, int, int]:
    """Convierte `#rgb` o `#rrggbb` en una tupla RGB 0-255. Lanza `ValueError` si no es hex."""
    if not isinstance(color, str) or not _HEX.match(color):
        raise ValueError(f"Color hexadecimal inválido: {color!r}")
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_a_hex(r: int, g: int, b: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, round(r))), max(0, min(255, round(g))), max(0, min(255, round(b)))
    )


def _canal_lineal(c8: int) -> float:
    """Linealiza un canal 0-255 según WCAG (corrección gamma sRGB)."""
    c = c8 / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminancia_relativa(color: str) -> float:
    """Luminancia relativa (0 negro, 1 blanco) según WCAG."""
    r, g, b = hex_a_rgb(color)
    return 0.2126 * _canal_lineal(r) + 0.7152 * _canal_lineal(g) + 0.0722 * _canal_lineal(b)


def ratio_contraste(a: str, b: str) -> float:
    """Relación de contraste WCAG entre dos colores (≥1). Simétrica en sus argumentos."""
    la, lb = luminancia_relativa(a), luminancia_relativa(b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


# --- Conversión HSL para derivar la escala de acento ------------------------

def _rgb_a_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
    rn, gn, bn = r / 255, g / 255, b / 255
    mx, mn = max(rn, gn, bn), min(rn, gn, bn)
    l = (mx + mn) / 2
    d = mx - mn
    if d == 0:
        return 0.0, 0.0, l
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == rn:
        h = ((gn - bn) / d) % 6
    elif mx == gn:
        h = (bn - rn) / d + 2
    else:
        h = (rn - gn) / d + 4
    return h * 60, s, l


def _hsl_a_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    if s == 0:
        v = round(l * 255)
        return v, v, v
    c = (1 - abs(2 * l - 1)) * s
    hp = (h % 360) / 60
    x = c * (1 - abs(hp % 2 - 1))
    if hp < 1:
        r, g, b = c, x, 0
    elif hp < 2:
        r, g, b = x, c, 0
    elif hp < 3:
        r, g, b = 0, c, x
    elif hp < 4:
        r, g, b = 0, x, c
    elif hp < 5:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    m = l - c / 2
    return round((r + m) * 255), round((g + m) * 255), round((b + m) * 255)


def _ajustar_luminosidad(color: str, delta_l: float, *, sat_max: float | None = None) -> str:
    h, s, l = _rgb_a_hsl(*hex_a_rgb(color))
    if sat_max is not None:
        s = min(s, sat_max)
    l = max(0.0, min(1.0, l + delta_l))
    return _rgb_a_hex(*_hsl_a_rgb(h, s, l))


def derivar_tokens_acento(acento: str) -> dict:
    """Deriva la escala de acento a partir del color base, ajustando la luminosidad.

    - `hover`: más oscuro (estado hover/activo).
    - `claro`: tinte muy claro (fondos tenues tipo `bg-indigo-50`).
    - `foco`: algo más claro que la base (anillo de foco).

    Con el acento por defecto (`#4338ca`) reproduce, aproximadamente, la escala índigo
    actual (`#3730a3` / `#eef2ff` / `#6366f1`).
    """
    return {
        "hover": _ajustar_luminosidad(acento, -0.12),
        "claro": _ajustar_luminosidad(acento, 0.95 - _rgb_a_hsl(*hex_a_rgb(acento))[2], sat_max=0.30),
        "foco": _ajustar_luminosidad(acento, 0.10),
    }


# Escalones de luminosidad de las tres paradas del banner respecto al acento.
# Cero o negativos (igual o más oscuro): al oscurecer sobre blanco solo aumenta el
# contraste, así que —cumpliendo el acento 4.5:1 con blanco— cada parada lo cumple
# por construcción. La parada inicial es el propio acento; el degradado ahonda hacia
# el final. Con el acento por defecto (`#4338ca`) da un índigo que se oscurece.
_BANNER_DELTAS = (0.0, -0.08, -0.16)


def derivar_degradado_banner(acento: str) -> dict:
    """Deriva las tres paradas (0/60/100 %) del degradado del banner a partir del acento.

    Monocromático: conserva el tono (H) y la saturación (S) del acento y baja la
    luminosidad en escalones hacia la parada final. Cada parada queda igual o más oscura
    que el acento, de modo que si el acento cumple 4.5:1 con el texto blanco, cada parada
    lo cumple también. Devuelve un dict con `desde`, `medio` y `hasta` (hex).
    """
    desde, medio, hasta = (_ajustar_luminosidad(acento, d) for d in _BANNER_DELTAS)
    return {"desde": desde, "medio": medio, "hasta": hasta}


def validar_paleta(
    acento: str,
    banner_desde: str,
    banner_medio: str,
    banner_hasta: str,
) -> ResultadoContraste | None:
    """Valida el conjunto completo de pares de contraste de la paleta propuesta.

    Devuelve `None` si toda la paleta cumple AA, o el primer `ResultadoContraste` que
    falla (par, ratio obtenido, mínimo exigido). Lanza `ValueError` si algún color no es
    hex válido.

    Pares comprobados:
    - texto de botón / texto de acento (blanco ↔ acento): 4.5:1
    - hover (blanco ↔ acento-hover): 4.5:1
    - texto de acento sobre fondo tenue (acento ↔ acento-claro): 4.5:1
    - anillo de foco vs fondo (acento-foco ↔ fondo): 3:1
    - texto blanco del banner vs cada parada del degradado: 4.5:1
    """
    tokens = derivar_tokens_acento(acento)
    comprobaciones: list[tuple[str, str, str, float]] = [
        ("Texto sobre el botón de acento", BLANCO, acento, AA_NORMAL),
        ("Estado hover del acento", BLANCO, tokens["hover"], AA_NORMAL),
        ("Texto de acento sobre fondo tenue", acento, tokens["claro"], AA_NORMAL),
        ("Anillo de foco sobre el fondo", tokens["foco"], FONDO, AA_GRANDE),
        ("Texto del banner sobre la parada inicial", BLANCO, banner_desde, AA_NORMAL),
        ("Texto del banner sobre la parada media", BLANCO, banner_medio, AA_NORMAL),
        ("Texto del banner sobre la parada final", BLANCO, banner_hasta, AA_NORMAL),
    ]
    for etiqueta, a, b, minimo in comprobaciones:
        ratio = ratio_contraste(a, b)
        if ratio < minimo:
            return ResultadoContraste(par=etiqueta, ratio=round(ratio, 2), minimo=minimo)
    return None
