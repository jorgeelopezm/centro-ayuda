"""Tests de extracción de texto por formato y del troceo."""

from __future__ import annotations

import io

import pytest

from app.troceo import (
    MAX_BYTES_DOCUMENTO,
    MIME_DOCX,
    MIME_MD,
    MIME_PDF,
    MIME_TXT,
    ArchivoInvalido,
    ExtraccionFallida,
    FormatoNoAdmitido,
    PALABRAS_POR_FRAGMENTO,
    PALABRAS_SOLAPE,
    extraer_texto,
    trocear,
    validar_subida,
)


# --- validar_subida --------------------------------------------------------


def test_validar_subida_acepta_mimes_admitidos():
    for mime in (MIME_PDF, MIME_DOCX, MIME_MD, MIME_TXT):
        assert validar_subida(mime, 100) == mime


def test_validar_subida_normaliza_alias_de_markdown():
    # Los alias históricos de Markdown se normalizan al canónico para persistirlo así.
    assert validar_subida("text/x-markdown", 100) == MIME_MD
    assert validar_subida("application/x-markdown", 100) == MIME_MD


def test_validar_subida_rechaza_formato_no_admitido():
    with pytest.raises(FormatoNoAdmitido):
        validar_subida("image/png", 100)


def test_validar_subida_rechaza_archivo_vacio():
    with pytest.raises(ArchivoInvalido):
        validar_subida(MIME_TXT, 0)


def test_validar_subida_rechaza_archivo_demasiado_grande():
    with pytest.raises(ArchivoInvalido):
        validar_subida(MIME_TXT, MAX_BYTES_DOCUMENTO + 1)


# --- extraer_texto: TXT y Markdown -----------------------------------------


def test_extraer_txt_utf8():
    contenido = "hola mundo".encode("utf-8")
    assert extraer_texto(contenido, MIME_TXT) == "hola mundo"


def test_extraer_txt_descarta_bom():
    # BOM UTF-8 al principio: no debe aparecer en el texto extraído.
    contenido = "﻿hola".encode("utf-8")
    assert extraer_texto(contenido, MIME_TXT) == "hola"


def test_extraer_md_como_texto_plano():
    contenido = "# Titulo\n\ntexto".encode("utf-8")
    assert extraer_texto(contenido, MIME_MD) == "# Titulo\n\ntexto"


# --- extraer_texto: DOCX (integración real con python-docx) ----------------


def _docx_de_ejemplo(parrafos: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for p in parrafos:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extraer_docx_devuelve_parrafos_separados():
    parrafos = ["Primer párrafo", "Segundo párrafo"]
    texto = extraer_texto(_docx_de_ejemplo(parrafos), MIME_DOCX)
    assert "Primer párrafo" in texto
    assert "Segundo párrafo" in texto
    assert "\n\n" in texto  # doble salto entre párrafos preserva el corte


def test_extraer_docx_corrupto_levanta_extraccion_fallida():
    with pytest.raises(ExtraccionFallida):
        extraer_texto(b"esto no es un DOCX", MIME_DOCX)


# --- trocear --------------------------------------------------------------


def test_trocear_texto_vacio_devuelve_lista_vacia():
    assert trocear("") == []
    assert trocear("   \n\n   ") == []


def test_trocear_texto_corto_devuelve_un_fragmento():
    texto = "Un párrafo pequeño.\n\nOtro párrafo pequeño."
    fragmentos = trocear(texto)
    assert len(fragmentos) == 1
    # Los dos párrafos originales caben en un solo fragmento.
    assert "Un párrafo pequeño." in fragmentos[0]
    assert "Otro párrafo pequeño." in fragmentos[0]


def _texto_de_n_palabras(n: int) -> str:
    """Devuelve un párrafo de `n` palabras separadas por espacios."""
    return " ".join(f"palabra{i}" for i in range(n))


def test_trocear_parrafo_grande_se_corta_por_palabras_con_solape():
    # Un párrafo de N palabras > PALABRAS_POR_FRAGMENTO: se trocea por palabras
    # con solape. El texto no cabe entero en un fragmento.
    n = PALABRAS_POR_FRAGMENTO + 300
    fragmentos = trocear(_texto_de_n_palabras(n))
    assert len(fragmentos) >= 2
    for fragmento in fragmentos:
        assert len(fragmento.split()) <= PALABRAS_POR_FRAGMENTO


def test_trocear_dos_parrafos_grandes_se_reparten_en_multiples_fragmentos():
    # Dos párrafos que juntos superan el tope: deben repartirse en al menos
    # dos fragmentos.
    parrafo = _texto_de_n_palabras(PALABRAS_POR_FRAGMENTO)
    fragmentos = trocear(f"{parrafo}\n\n{parrafo}")
    assert len(fragmentos) >= 2


def test_trocear_solape_entre_fragmentos_no_vacio():
    # Dos párrafos de tamaño tal que rebasan el tope al añadir el segundo.
    parrafo = _texto_de_n_palabras(int(PALABRAS_POR_FRAGMENTO * 0.7))
    fragmentos = trocear(f"{parrafo}\n\n{parrafo}")
    assert len(fragmentos) >= 2
    # El segundo fragmento arranca con el solape del primero: la primera palabra
    # del segundo aparece también entre las últimas del primero.
    ultimas_del_primero = fragmentos[0].split()[-PALABRAS_SOLAPE:]
    primera_del_segundo = fragmentos[1].split()[0]
    assert primera_del_segundo in ultimas_del_primero
