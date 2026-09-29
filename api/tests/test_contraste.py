"""Contraste WCAG y derivación de la escala de acento (lógica pura)."""

from __future__ import annotations

import pytest

from app.contraste import (
    AA_NORMAL,
    BLANCO,
    derivar_degradado_banner,
    derivar_tokens_acento,
    hex_a_rgb,
    luminancia_relativa,
    ratio_contraste,
    validar_paleta,
)

# Acentos que superan la validación COMPLETA de paleta (botón, tinte, foco). Un gris muy
# desaturado como #767676 cumple 4.5:1 con blanco pero falla el par acento/tinte, así que
# no es un acento de marca válido; su caso límite se prueba aparte solo contra el blanco.
ACENTOS_VALIDOS = ("#4338ca", "#0f766e", "#b91c1c", "#7c3aed", "#1d4ed8")

# Paleta por defecto (aspecto índigo actual): debe cumplir toda la validación.
ACENTO_DEFECTO = "#4338ca"
BANNER_DEFECTO = ("#3730a3", "#4338ca", "#4f46e5")


# --- Fórmulas ----------------------------------------------------------------

def test_hex_de_tres_digitos_se_expande():
    assert hex_a_rgb("#fff") == (255, 255, 255)
    assert hex_a_rgb("#000") == (0, 0, 0)


def test_hex_invalido_lanza():
    for malo in ("blanco", "#12", "#1234", "rgb(0,0,0)", "#ggghhh"):
        with pytest.raises(ValueError):
            hex_a_rgb(malo)


def test_luminancia_extremos():
    assert luminancia_relativa("#000000") == pytest.approx(0.0, abs=1e-6)
    assert luminancia_relativa("#ffffff") == pytest.approx(1.0, abs=1e-6)


def test_ratio_blanco_negro_es_21():
    assert ratio_contraste("#000000", "#ffffff") == pytest.approx(21.0, abs=0.05)


def test_ratio_es_simetrico():
    assert ratio_contraste("#4338ca", "#ffffff") == pytest.approx(
        ratio_contraste("#ffffff", "#4338ca")
    )


def test_gris_limite_aa():
    # #767676 sobre blanco es el gris clásico que roza el mínimo 4.5:1.
    assert ratio_contraste("#767676", "#ffffff") == pytest.approx(4.54, abs=0.1)
    assert ratio_contraste("#767676", "#ffffff") >= AA_NORMAL
    # Un tono un pelín más claro ya no llega.
    assert ratio_contraste("#787878", "#ffffff") < AA_NORMAL


# --- Derivación de tokens ----------------------------------------------------

def test_derivacion_devuelve_hex_validos():
    tokens = derivar_tokens_acento(ACENTO_DEFECTO)
    assert set(tokens) == {"hover", "claro", "foco"}
    for valor in tokens.values():
        assert hex_a_rgb(valor)  # no lanza => hex válido


def test_hover_mas_oscuro_y_claro_mas_luminoso_que_la_base():
    tokens = derivar_tokens_acento(ACENTO_DEFECTO)
    base = luminancia_relativa(ACENTO_DEFECTO)
    assert luminancia_relativa(tokens["hover"]) < base
    assert luminancia_relativa(tokens["claro"]) > base


# --- Derivación del degradado del banner -------------------------------------

def test_degradado_devuelve_tres_paradas_hex_validas():
    banner = derivar_degradado_banner(ACENTO_DEFECTO)
    assert set(banner) == {"desde", "medio", "hasta"}
    for valor in banner.values():
        assert hex_a_rgb(valor)  # no lanza => hex válido


def test_parada_inicial_es_el_propio_acento():
    assert derivar_degradado_banner(ACENTO_DEFECTO)["desde"] == ACENTO_DEFECTO


def test_reproduce_la_referencia_compartida_con_el_cliente():
    # Misma referencia que el espejo TS (contraste.test.ts): misma fórmula ⇒ mismo hex.
    assert derivar_degradado_banner(ACENTO_DEFECTO) == {
        "desde": "#4338ca",
        "medio": "#372eac",
        "hasta": "#2d258b",
    }


@pytest.mark.parametrize("acento", ACENTOS_VALIDOS)
def test_cada_parada_cumple_contraste_con_blanco(acento):
    # Precondición: el acento cumple 4.5:1 con el texto blanco.
    assert ratio_contraste(BLANCO, acento) >= AA_NORMAL
    for parada in derivar_degradado_banner(acento).values():
        assert ratio_contraste(BLANCO, parada) >= AA_NORMAL


@pytest.mark.parametrize("acento", ACENTOS_VALIDOS)
def test_luminosidad_decrece_hacia_el_final(acento):
    banner = derivar_degradado_banner(acento)
    lum = [luminancia_relativa(banner[k]) for k in ("desde", "medio", "hasta")]
    assert lum[0] >= lum[1] >= lum[2]


@pytest.mark.parametrize("acento", ACENTOS_VALIDOS)
def test_el_degradado_derivado_valida_la_paleta(acento):
    banner = derivar_degradado_banner(acento)
    assert validar_paleta(acento, banner["desde"], banner["medio"], banner["hasta"]) is None


def test_acento_en_el_borde_de_45_da_paradas_accesibles():
    # #767676 roza el mínimo 4.5:1 con blanco; las paradas (más oscuras) lo mantienen.
    banner = derivar_degradado_banner("#767676")
    for parada in banner.values():
        assert ratio_contraste(BLANCO, parada) >= AA_NORMAL


# --- Validación de la paleta -------------------------------------------------

def test_paleta_por_defecto_cumple():
    assert validar_paleta(ACENTO_DEFECTO, *BANNER_DEFECTO) is None


def test_acento_demasiado_claro_falla_el_boton():
    fallo = validar_paleta("#cccccc", *BANNER_DEFECTO)
    assert fallo is not None
    assert "botón" in fallo.par.lower()
    assert fallo.ratio < fallo.minimo
    assert fallo.minimo == AA_NORMAL


def test_banner_demasiado_claro_falla():
    # La parada final blanca-amarillenta no contrasta con el texto blanco.
    fallo = validar_paleta(ACENTO_DEFECTO, "#3730a3", "#4338ca", "#fffbe6")
    assert fallo is not None
    assert "banner" in fallo.par.lower()


def test_color_invalido_en_la_paleta_lanza():
    with pytest.raises(ValueError):
        validar_paleta("no-es-hex", *BANNER_DEFECTO)
