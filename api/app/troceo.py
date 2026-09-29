"""Extracción de texto por formato y troceo en fragmentos para el índice RAG.

Vive fuera de `servicios_ia.py` porque no habla con la red: transforma bytes a
texto y texto a fragmentos ordenados. La ingesta (`ingesta.py`) los enlaza con
el embedding y la persistencia.

Formatos admitidos:

- **PDF** con `pypdf`.
- **DOCX** con `python-docx`.
- **Markdown** y **TXT** como texto plano (UTF-8 con reemplazo tolerante).

Cualquier otro mime se rechaza en `validar_subida` antes de crear el documento.

Parámetros iniciales de troceo (constantes ajustables): ~800 palabras por
fragmento y ~15% de solape, con cortes por límite de párrafo cuando cabe. Las
«palabras» aproximan tokens (los proveedores tokenizan distinto; una cota por
palabras basta para acotar el tamaño del fragmento sin acoplarse al tokenizador
del proveedor). Se ajustan cuando exista la recuperación para medir calidad.
"""

from __future__ import annotations

import io

# Mime types que se aceptan. Se comparan con el `Content-Type` de la subida.
# Los `application/x-markdown` y `text/x-markdown` se aceptan también como
# Markdown por compatibilidad histórica (algunos clientes mandan variantes).
MIME_PDF = "application/pdf"
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_MD = "text/markdown"
MIME_TXT = "text/plain"

_MIMES_MD_ALIAS = frozenset({"text/x-markdown", "application/x-markdown"})
MIMES_ADMITIDOS = frozenset({MIME_PDF, MIME_DOCX, MIME_MD, MIME_TXT}) | _MIMES_MD_ALIAS

# Tamaño máximo del archivo subido (bytes). Cota baja para evitar OOM en la
# extracción y payloads absurdos que consumirían al proveedor de embeddings.
MAX_BYTES_DOCUMENTO = 10 * 1024 * 1024  # 10 MiB

# Parámetros del troceo. "Palabras" aproxima tokens: los proveedores tokenizan
# distinto y no vale la pena atar el troceo a un tokenizador concreto.
PALABRAS_POR_FRAGMENTO = 800
PALABRAS_SOLAPE = 120  # ~15%


class ErrorSubida(ValueError):
    """Base de los errores de validación de una subida (mime o tamaño)."""


class FormatoNoAdmitido(ErrorSubida):
    """El archivo tiene un mime que la ingesta no acepta."""


class ArchivoInvalido(ErrorSubida):
    """El archivo está vacío o supera `MAX_BYTES_DOCUMENTO`."""


class ExtraccionFallida(RuntimeError):
    """El archivo es del formato correcto pero no se pudo leer su texto."""


def _normalizar_mime(mime: str) -> str:
    """Colapsa alias de Markdown al mime canónico, para almacenamiento y comparación."""
    return MIME_MD if mime in _MIMES_MD_ALIAS else mime


def validar_subida(mime: str, tamanio_bytes: int) -> str:
    """Valida mime y tamaño antes de crear el `Documento` en la base.

    Devuelve el mime **normalizado** (para guardar el canónico, no los alias).
    """
    if mime not in MIMES_ADMITIDOS:
        raise FormatoNoAdmitido(f"Formato no admitido: {mime}.")
    if tamanio_bytes == 0:
        raise ArchivoInvalido("El archivo está vacío.")
    if tamanio_bytes > MAX_BYTES_DOCUMENTO:
        raise ArchivoInvalido(
            f"El archivo supera el tamaño máximo "
            f"({MAX_BYTES_DOCUMENTO // 1024 // 1024} MB)."
        )
    return _normalizar_mime(mime)


def extraer_texto(datos: bytes, mime: str) -> str:
    """Devuelve el texto crudo del documento, descartando metadatos y binarios.

    Puede levantar `ExtraccionFallida` si el archivo es del formato correcto
    pero está corrupto. `FormatoNoAdmitido` si el mime no es aceptado (defensa
    para llamadores que no hayan pasado por `validar_subida`).
    """
    canonico = _normalizar_mime(mime)
    if canonico == MIME_PDF:
        return _extraer_pdf(datos)
    if canonico == MIME_DOCX:
        return _extraer_docx(datos)
    if canonico in (MIME_MD, MIME_TXT):
        # UTF-8 con `replace`: no perder el documento entero por un byte malo.
        # Si el archivo tiene BOM (U+FEFF), se descarta para no ensuciar el
        # troceo por párrafos con un carácter invisible al principio.
        return datos.decode("utf-8", errors="replace").lstrip("﻿")
    raise FormatoNoAdmitido(f"Formato no admitido: {mime}.")


def _extraer_pdf(datos: bytes) -> str:
    from pypdf import PdfReader

    try:
        lector = PdfReader(io.BytesIO(datos))
        paginas = [(pagina.extract_text() or "") for pagina in lector.pages]
    except Exception as exc:  # noqa: BLE001 - pypdf lanza tipos distintos
        raise ExtraccionFallida(f"No se pudo leer el PDF: {exc}") from exc
    # Doble salto entre páginas preserva el corte para el troceo por párrafos.
    return "\n\n".join(paginas)


def _extraer_docx(datos: bytes) -> str:
    # `python-docx` acepta ruta o un buffer con `read()`.
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ExtraccionFallida("El paquete `python-docx` no está instalado.") from exc
    try:
        doc = Document(io.BytesIO(datos))
    except Exception as exc:  # noqa: BLE001 - python-docx lanza tipos distintos
        raise ExtraccionFallida(f"No se pudo leer el DOCX: {exc}") from exc
    return "\n\n".join(p.text for p in doc.paragraphs if p.text)


def trocear(texto: str) -> list[str]:
    """Divide `texto` en fragmentos de ~800 palabras con ~15% de solape.

    Estrategia:

    - Separa por párrafos (líneas en blanco).
    - Acumula párrafos en un fragmento hasta rozar el tope; el siguiente
      fragmento arranca con las últimas `PALABRAS_SOLAPE` palabras del
      anterior para mantener la continuidad semántica.
    - Un párrafo más grande que un fragmento entero se corta por palabras
      (mantiene el solape). Romper la palabra sería peor que cortar el párrafo.

    Devuelve una lista vacía si `texto` no aporta contenido: la ingesta lo
    trata como `error` (nada que indexar).
    """
    limpio = texto.replace("\r\n", "\n").strip()
    if not limpio:
        return []

    parrafos = [p.strip() for p in limpio.split("\n\n") if p.strip()]
    fragmentos: list[str] = []
    buffer: list[str] = []
    palabras_buffer = 0
    paso = PALABRAS_POR_FRAGMENTO - PALABRAS_SOLAPE

    for parrafo in parrafos:
        palabras = parrafo.split()
        n = len(palabras)

        # Un párrafo por sí solo excede el tope: cierra el fragmento actual y
        # trocea el párrafo por palabras con el mismo solape.
        if n > PALABRAS_POR_FRAGMENTO:
            if buffer:
                fragmentos.append("\n\n".join(buffer))
                buffer = []
                palabras_buffer = 0
            for i in range(0, n, paso):
                trozo = palabras[i : i + PALABRAS_POR_FRAGMENTO]
                fragmentos.append(" ".join(trozo))
                if i + PALABRAS_POR_FRAGMENTO >= n:
                    break
            continue

        # Añadirlo sobrepasa el tope: cierra y arranca el siguiente con solape.
        if buffer and palabras_buffer + n > PALABRAS_POR_FRAGMENTO:
            fragmentos.append("\n\n".join(buffer))
            solape = " ".join(" ".join(buffer).split()[-PALABRAS_SOLAPE:])
            buffer = [solape] if solape else []
            palabras_buffer = len(solape.split())

        buffer.append(parrafo)
        palabras_buffer += n

    if buffer:
        fragmentos.append("\n\n".join(buffer))
    return fragmentos


def texto_de_articulo(traduccion) -> str:
    """Ensambla el texto de una `ArticuloTraduccion` para el troceo.

    Junta título, párrafos, pasos de `how_to` y preguntas/respuestas de `faq`
    en un solo texto plano con dobles saltos entre bloques, para que el troceo
    por párrafos funcione igual que con un documento subido. La `nota` se
    incluye si está.

    Este es el pegamento entre la escritura de artículos (`servicios.py`) y el
    troceo: el mismo pipeline sirve para documentos y artículos.
    """
    partes: list[str] = [traduccion.titulo]
    for parrafo in traduccion.parrafos or []:
        if parrafo:
            partes.append(parrafo)
    how_to = traduccion.how_to or {}
    titulo_ht = how_to.get("titulo") if isinstance(how_to, dict) else None
    if titulo_ht:
        partes.append(titulo_ht)
    for paso in (how_to.get("pasos") if isinstance(how_to, dict) else None) or []:
        titulo_paso = paso.get("titulo") if isinstance(paso, dict) else None
        desc = paso.get("descripcion") if isinstance(paso, dict) else None
        if titulo_paso and desc:
            partes.append(f"{titulo_paso}. {desc}")
        elif titulo_paso:
            partes.append(titulo_paso)
        elif desc:
            partes.append(desc)
    if traduccion.nota:
        partes.append(traduccion.nota)
    for item in traduccion.faq or []:
        pregunta = item.get("pregunta") if isinstance(item, dict) else None
        respuesta = item.get("respuesta") if isinstance(item, dict) else None
        if pregunta and respuesta:
            partes.append(f"{pregunta}\n{respuesta}")
        elif pregunta:
            partes.append(pregunta)
        elif respuesta:
            partes.append(respuesta)
    return "\n\n".join(partes)
