"""Recuperación vectorial acotada al portal del host (RAG del chat).

Busca fragmentos relevantes en `articulo_chunks` y `documento_chunks` para una
consulta dada, filtrando **exclusivamente** por el `portal_id` resuelto del host
(la única fuente de verdad del tenant; ver `app.deps.portal_actual`). El
`portal_id` no se acepta del cuerpo, ruta ni cabecera del cliente: la función
solo lo recibe del router, que lo resuelve del host.

Los fragmentos de artículo se filtran también por el idioma de la consulta
(cada traducción se indexa por separado); los de documento no llevan filtro de
idioma porque no lo tienen (son binarios subidos por Administrador; ver el
modelo `Documento`).

En PostgreSQL usa pgvector con distancia coseno; en SQLite (tests) cae a un
cálculo en Python sobre el vector materializado como lista. La misma firma
pública (`recuperar`) vale para ambos motores, así que el pipeline del chat no
necesita saber dónde corre.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ArticuloChunk, ArticuloTraduccion, Documento, DocumentoChunk
from app.servicios_ia import ErrorTraduccion, crear_embedder

logger = logging.getLogger(__name__)

Veredicto = Literal["ok", "sin_resultados", "error_proveedor"]
TipoFragmento = Literal["articulo", "documento"]


@dataclass
class FragmentoRecuperado:
    """Fragmento devuelto por el recuperador con las claves para reconstruir la cita.

    `origen` guarda las claves de origen suficientes para que el pipeline del
    chat pueda enlazar la cita al artículo o documento correspondiente sin
    volver a la base:
    - `articulo`: `{"articulo_id": str, "idioma": str, "titulo": str, "slug": str}`
    - `documento`: `{"documento_id": int, "nombre": str}`

    `portal_id` se guarda explícitamente para que el pipeline pueda VOLVER a
    validar que ninguna cita cruzó de tenant (defensa en profundidad; el filtro
    de la consulta ya lo garantiza).
    """

    tipo: TipoFragmento
    portal_id: str
    orden: int
    texto: str
    similitud: float
    origen: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoRecuperacion:
    fragmentos: list[FragmentoRecuperado]
    veredicto: Veredicto
    # `detalle` describe el motivo genérico de un `error_proveedor` (para logs
    # internos y para que el pipeline decida cómo reportar); NUNCA expone
    # detalles del proveedor al cliente.
    detalle: str | None = None


def recuperar(
    consulta: str,
    idioma: str,
    portal_id: str,
    db: Session,
) -> ResultadoRecuperacion:
    """Recupera fragmentos relevantes para `consulta` acotados al portal.

    - Genera el embedding de la consulta con el `ProveedorEmbeddings`
      configurado (Voyage AI `voyage-3` por defecto).
    - Une `articulo_chunks` (filtrado por `portal_id` y `idioma`) con
      `documento_chunks` (filtrado por `portal_id`) y ordena por similitud
      coseno.
    - Aplica `RAG_TOP_K` y `RAG_UMBRAL_SIMILITUD` de `Settings`.
    - Si ningún fragmento supera el umbral, devuelve `sin_resultados` (sin colar
      candidatos por debajo).
    - Si el embedder falla, devuelve `error_proveedor` con detalle genérico; el
      pipeline del chat lo mapea a `escalar` con `razon: error_proveedor`.
    """
    settings = get_settings()

    try:
        embedder = crear_embedder(db)
        vectores = embedder.embeber([consulta])
    except ErrorTraduccion as exc:
        # Base común de `ErrorProveedor` y `ProveedorNoConfigurado`. El detalle del
        # proveedor va al log (no a la respuesta): un embebedor caído degrada en
        # silencio a `sin_resultados` en el chat y a "redactar sin contexto" en las
        # sugerencias, así que sin esto no queda rastro de la causa.
        logger.warning("Recuperador: fallo del embedder (%s): %s", type(exc).__name__, exc)
        return ResultadoRecuperacion(fragmentos=[], veredicto="error_proveedor", detalle="embedder")

    if not vectores or not vectores[0]:
        return ResultadoRecuperacion(fragmentos=[], veredicto="error_proveedor", detalle="embedder")

    vector_consulta = vectores[0]
    dialecto = db.bind.dialect.name if db.bind is not None else ""
    # `uuid.UUID(...)`: `portal_id` llega como `str` del router; las columnas
    # `portal_id` de `articulo_chunks`/`documento_chunks` son `uuid.UUID`
    # (columna `Uuid`) y SQLAlchemy exige el tipo Python nativo al enlazar el
    # parámetro (falla con `AttributeError: 'str' object has no attribute
    # 'hex'` en SQLite si se le pasa una cadena).
    portal_id_uuid = uuid.UUID(portal_id)

    if dialecto == "postgresql":
        candidatos = _buscar_postgres(db, vector_consulta, portal_id_uuid, idioma, settings.rag_top_k)
    else:
        candidatos = _buscar_python(db, vector_consulta, portal_id_uuid, idioma, settings.rag_top_k)

    filtrados = [f for f in candidatos if f.similitud >= settings.rag_umbral_similitud]
    if not filtrados:
        return ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados")

    return ResultadoRecuperacion(fragmentos=filtrados[: settings.rag_top_k], veredicto="ok")


def _buscar_postgres(
    db: Session,
    vector: list[float],
    portal_id: uuid.UUID,
    idioma: str,
    top_k: int,
) -> list[FragmentoRecuperado]:
    """Búsqueda vectorial con pgvector (distancia coseno).

    Se hacen dos consultas separadas (una por tabla) y se fusionan en Python
    por similitud: mezclar dos tablas heterogéneas en un solo SQL con UNION y
    ORDER BY sobre `<=>` complica el operador y los índices HNSW. Cada tabla ya
    tiene su índice HNSW por coseno (`0008_rag_chunks`), así que dos hits
    baratos + ordenación en Python de `2·top_k` filas es simple y suficiente.
    """
    # `<=>` es la distancia coseno de pgvector (0 = idéntico, 2 = opuesto).
    # `similitud = 1 - distancia` la convierte al intervalo intuitivo [-1, 1]
    # (para vectores no negativos, [0, 1]).
    from sqlalchemy import select  # local: no forzar import en SQLite

    articulos: list[FragmentoRecuperado] = []
    stmt_art = (
        select(
            ArticuloChunk.portal_id,
            ArticuloChunk.articulo_id,
            ArticuloChunk.idioma,
            ArticuloChunk.orden,
            ArticuloChunk.contenido,
            ArticuloChunk.embedding.cosine_distance(vector).label("distancia"),
        )
        .where(ArticuloChunk.portal_id == portal_id, ArticuloChunk.idioma == idioma)
        .order_by("distancia")
        .limit(top_k)
    )
    filas_art = db.execute(stmt_art).all()
    # Un solo join a `articulo_traducciones` para hidratar título y slug de las
    # citas (evita `top_k` peticiones separadas).
    if filas_art:
        ids = {(f.portal_id, f.articulo_id, f.idioma) for f in filas_art}
        traducciones = _cargar_traducciones(db, ids)
        for f in filas_art:
            trad = traducciones.get((f.portal_id, f.articulo_id, f.idioma), (None, None))
            articulos.append(
                FragmentoRecuperado(
                    tipo="articulo",
                    # `str(...)`: `ArticuloChunk.portal_id` es un `uuid.UUID`; el pipeline
                    # compara este campo contra el `portal_id` (str) del host más adelante.
                    portal_id=str(f.portal_id),
                    orden=f.orden,
                    texto=f.contenido,
                    similitud=1.0 - float(f.distancia),
                    origen={
                        "articulo_id": f.articulo_id,
                        "idioma": f.idioma,
                        "titulo": trad[0],
                        "slug": trad[1],
                    },
                )
            )

    documentos: list[FragmentoRecuperado] = []
    stmt_doc = (
        select(
            DocumentoChunk.portal_id,
            DocumentoChunk.documento_id,
            DocumentoChunk.orden,
            DocumentoChunk.contenido,
            DocumentoChunk.embedding.cosine_distance(vector).label("distancia"),
        )
        .where(DocumentoChunk.portal_id == portal_id)
        .order_by("distancia")
        .limit(top_k)
    )
    filas_doc = db.execute(stmt_doc).all()
    if filas_doc:
        doc_ids = {f.documento_id for f in filas_doc}
        nombres = _cargar_nombres_documento(db, doc_ids)
        for f in filas_doc:
            documentos.append(
                FragmentoRecuperado(
                    tipo="documento",
                    # `str(...)`: `DocumentoChunk.portal_id` es un `uuid.UUID`; ídem el
                    # comentario del caso "articulo" arriba.
                    portal_id=str(f.portal_id),
                    orden=f.orden,
                    texto=f.contenido,
                    similitud=1.0 - float(f.distancia),
                    origen={
                        "documento_id": f.documento_id,
                        "nombre": nombres.get(f.documento_id, ""),
                    },
                )
            )

    todos = articulos + documentos
    todos.sort(key=lambda f: f.similitud, reverse=True)
    return todos[: top_k * 2]  # el filtro de umbral se aplica en `recuperar`


def _buscar_python(
    db: Session,
    vector: list[float],
    portal_id: uuid.UUID,
    idioma: str,
    top_k: int,
) -> list[FragmentoRecuperado]:
    """Fallback para SQLite (tests): materializa vectores como lista y calcula
    coseno en Python. Suficiente para volúmenes de prueba; el motor real es
    pgvector con HNSW."""
    articulos: list[FragmentoRecuperado] = []
    filas_art = (
        db.query(ArticuloChunk)
        .filter(ArticuloChunk.portal_id == portal_id, ArticuloChunk.idioma == idioma)
        .all()
    )
    if filas_art:
        ids = {(f.portal_id, f.articulo_id, f.idioma) for f in filas_art}
        traducciones = _cargar_traducciones(db, ids)
        for f in filas_art:
            embedding = f.embedding if isinstance(f.embedding, list) else list(f.embedding or [])
            similitud = _coseno(vector, embedding)
            trad = traducciones.get((f.portal_id, f.articulo_id, f.idioma), (None, None))
            articulos.append(
                FragmentoRecuperado(
                    tipo="articulo",
                    # `str(...)`: `ArticuloChunk.portal_id` es un `uuid.UUID`; el pipeline
                    # compara este campo contra el `portal_id` (str) del host más adelante.
                    portal_id=str(f.portal_id),
                    orden=f.orden,
                    texto=f.contenido,
                    similitud=similitud,
                    origen={
                        "articulo_id": f.articulo_id,
                        "idioma": f.idioma,
                        "titulo": trad[0],
                        "slug": trad[1],
                    },
                )
            )

    documentos: list[FragmentoRecuperado] = []
    filas_doc = (
        db.query(DocumentoChunk)
        .filter(DocumentoChunk.portal_id == portal_id)
        .all()
    )
    if filas_doc:
        doc_ids = {f.documento_id for f in filas_doc}
        nombres = _cargar_nombres_documento(db, doc_ids)
        for f in filas_doc:
            embedding = f.embedding if isinstance(f.embedding, list) else list(f.embedding or [])
            similitud = _coseno(vector, embedding)
            documentos.append(
                FragmentoRecuperado(
                    tipo="documento",
                    # `str(...)`: `DocumentoChunk.portal_id` es un `uuid.UUID`; ídem el
                    # comentario del caso "articulo" arriba.
                    portal_id=str(f.portal_id),
                    orden=f.orden,
                    texto=f.contenido,
                    similitud=similitud,
                    origen={
                        "documento_id": f.documento_id,
                        "nombre": nombres.get(f.documento_id, ""),
                    },
                )
            )

    todos = articulos + documentos
    todos.sort(key=lambda f: f.similitud, reverse=True)
    return todos[: top_k * 2]


def _cargar_traducciones(
    db: Session,
    ids: set[tuple[str, str, str]],
) -> dict[tuple[str, str, str], tuple[str, str]]:
    """Carga `(titulo, slug)` de cada `(portal_id, articulo_id, idioma)` en un
    diccionario para hidratar las citas sin `N+1` consultas."""
    if not ids:
        return {}
    portal_ids = {i[0] for i in ids}
    articulo_ids = {i[1] for i in ids}
    idiomas = {i[2] for i in ids}
    filas = (
        db.query(
            ArticuloTraduccion.portal_id,
            ArticuloTraduccion.articulo_id,
            ArticuloTraduccion.idioma,
            ArticuloTraduccion.titulo,
            ArticuloTraduccion.slug,
        )
        .filter(
            ArticuloTraduccion.portal_id.in_(portal_ids),
            ArticuloTraduccion.articulo_id.in_(articulo_ids),
            ArticuloTraduccion.idioma.in_(idiomas),
        )
        .all()
    )
    return {(f.portal_id, f.articulo_id, f.idioma): (f.titulo, f.slug) for f in filas}


def _cargar_nombres_documento(db: Session, doc_ids: set[int]) -> dict[int, str]:
    if not doc_ids:
        return {}
    filas = (
        db.query(Documento.id, Documento.nombre)
        .filter(Documento.id.in_(doc_ids))
        .all()
    )
    return {f.id: f.nombre for f in filas}


def _coseno(a: list[float], b: list[float]) -> float:
    """Similitud coseno entre dos vectores. Devuelve 0 si algún vector es nulo."""
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db_ = math.sqrt(sum(y * y for y in b))
    if da == 0.0 or db_ == 0.0:
        return 0.0
    return num / (da * db_)
