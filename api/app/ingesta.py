"""Orquestador de ingesta de documentos y re-embedido de artículos.

Ata las tres piezas que ya viven en módulos separados:

- **Extracción y troceo** en `app.troceo` (sin red).
- **Embedding** en `app.servicios_ia` (un `ProveedorEmbeddings`).
- **Persistencia** en `app.models` (fragmentos por portal).

Las funciones se lanzan desde el router con `BackgroundTasks` para no bloquear
la respuesta HTTP. Cada corrutina gestiona su propia `Session` (el `db` que
inyecta FastAPI se cierra al terminar la petición: no vive dentro del
background), y cada una es responsable de transicionar el estado del
`Documento` en la base y de no dejar fragmentos parciales si algo falla.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ArticuloChunk, ArticuloTraduccion, Documento, DocumentoChunk
from app.servicios_ia import (
    ErrorTraduccion,
    ProveedorEmbeddings,
    crear_embedder,
)
from app.troceo import ExtraccionFallida, extraer_texto, texto_de_articulo, trocear

if TYPE_CHECKING:
    from app.models import Articulo


logger = logging.getLogger(__name__)


# Fábrica del embedder: por defecto se resuelve desde `ConfigIA`. Los tests la
# sustituyen por una fábrica que devuelve un doble determinista, evitando red y
# clave real (`inyectar_embedder_factory`). No es una dependencia de FastAPI:
# las funciones de ingesta corren fuera de la petición.
_FabricaEmbedder = Callable[[Session], ProveedorEmbeddings]
_fabrica_embedder: _FabricaEmbedder = crear_embedder


def inyectar_embedder_factory(fabrica: _FabricaEmbedder) -> None:
    """Reemplaza la fábrica de embedder (solo para tests)."""
    global _fabrica_embedder
    _fabrica_embedder = fabrica


def restaurar_embedder_factory() -> None:
    """Restaura la fábrica por defecto (tests)."""
    global _fabrica_embedder
    _fabrica_embedder = crear_embedder


# Fábrica de sesión: por defecto es la `SessionLocal` de producción. Los tests
# la sustituyen para que las funciones de ingesta escriban en la base SQLite en
# memoria de la prueba (el override de `get_db` de FastAPI solo aplica a las
# dependencias del router; el background abre su propia sesión).
_FabricaSesion = Callable[[], Session]
_fabrica_sesion: _FabricaSesion = SessionLocal


def inyectar_sesion_factory(fabrica: _FabricaSesion) -> None:
    """Reemplaza la fábrica de sesión (solo para tests)."""
    global _fabrica_sesion
    _fabrica_sesion = fabrica


def restaurar_sesion_factory() -> None:
    """Restaura la fábrica por defecto (tests)."""
    global _fabrica_sesion
    _fabrica_sesion = SessionLocal


@contextmanager
def _sesion():
    """Sesión de SQLAlchemy propia del background (la de la petición ya cerró).

    Se hace commit/rollback dentro de las funciones de ingesta; aquí solo se
    garantiza el cierre.
    """
    db = _fabrica_sesion()
    try:
        yield db
    finally:
        db.close()


def _marcar_error(db: Session, documento_id: int, detalle: str) -> None:
    """Marca el documento como `error` con detalle legible, sin fragmentos.

    Se recarga la fila en su propia sesión: si algo falló en medio de la
    ingesta, la sesión previa puede estar en estado sucio y hay que salir de
    ella para actualizar el estado limpiamente.
    """
    documento = db.get(Documento, documento_id)
    if documento is None:
        return
    documento.estado = "error"
    documento.error_detalle = detalle[:500]  # cota: `error_detalle` es String
    db.commit()


def _borrar_fragmentos_documento(db: Session, documento_id: int) -> None:
    """Elimina cualquier fragmento del documento (recuperación tras fallo)."""
    (
        db.query(DocumentoChunk)
        .filter(DocumentoChunk.documento_id == documento_id)
        .delete(synchronize_session=False)
    )


def ingerir_documento(documento_id: int, contenido: bytes) -> None:
    """Ejecuta la ingesta completa de un documento.

    Pasos: extraer texto → trocear → embeber → persistir fragmentos. Transiciona
    el estado `pendiente → procesando → listo | error`. En caso de fallo, no
    quedan fragmentos parciales del documento (los borra el mismo commit
    fallido, con rollback + limpieza defensiva).

    Se llama desde `BackgroundTasks` del router. Recibe el binario porque el
    documento no se persiste (design.md D7): se descarta tras extraer texto.
    """
    with _sesion() as db:
        documento = db.get(Documento, documento_id)
        if documento is None:
            logger.warning("Documento %s no existe al iniciar la ingesta", documento_id)
            return
        documento.estado = "procesando"
        db.commit()

        try:
            texto = extraer_texto(contenido, documento.mime)
            fragmentos = trocear(texto)
            if not fragmentos:
                raise ExtraccionFallida(
                    "El documento no contiene texto legible tras el troceo."
                )
            embedder = _fabrica_embedder(db)
            vectores = embedder.embeber(fragmentos)
            if len(vectores) != len(fragmentos):
                raise RuntimeError(
                    "El proveedor de embeddings devolvió un número distinto de "
                    "vectores que de fragmentos."
                )
            # Todo o nada: se persiste dentro de una transacción atómica; el
            # rollback deja el documento sin fragmentos huérfanos.
            for orden, (fragmento, vector) in enumerate(zip(fragmentos, vectores)):
                db.add(
                    DocumentoChunk(
                        portal_id=documento.portal_id,
                        documento_id=documento.id,
                        orden=orden,
                        contenido=fragmento,
                        embedding=vector,
                    )
                )
            documento.estado = "listo"
            documento.error_detalle = None
            db.commit()
        except (ExtraccionFallida, ErrorTraduccion, RuntimeError) as exc:
            logger.warning("Ingesta de documento %s falló: %s", documento_id, exc)
            db.rollback()
            _borrar_fragmentos_documento(db, documento_id)
            db.commit()
            _marcar_error(db, documento_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - captura defensiva del background
            logger.exception("Ingesta de documento %s: error inesperado", documento_id)
            db.rollback()
            _borrar_fragmentos_documento(db, documento_id)
            db.commit()
            _marcar_error(db, documento_id, f"Error inesperado: {exc}")


def reindexar_articulo(portal_id: str, articulo_id: str) -> None:
    """Regenera los `articulo_chunks` de un artículo por idioma.

    Se llama desde `BackgroundTasks` tras `aplicar_datos_articulo` (crear o
    editar). Borra los fragmentos existentes del artículo y los reemplaza por
    los nuevos, dentro de una sola transacción. Si el embedder falla, se hace
    rollback y no se toca el índice existente (los fragmentos previos siguen
    en pie).
    """
    with _sesion() as db:
        traducciones = (
            db.query(ArticuloTraduccion)
            .filter(
                ArticuloTraduccion.portal_id == portal_id,
                ArticuloTraduccion.articulo_id == articulo_id,
            )
            .all()
        )
        if not traducciones:
            # El artículo pudo borrarse entre el guardado y este background.
            return

        try:
            embedder = _fabrica_embedder(db)
            nuevos_fragmentos: list[ArticuloChunk] = []
            for traduccion in traducciones:
                texto = texto_de_articulo(traduccion)
                fragmentos = trocear(texto)
                if not fragmentos:
                    continue
                vectores = embedder.embeber(fragmentos)
                if len(vectores) != len(fragmentos):
                    raise RuntimeError(
                        "El proveedor de embeddings devolvió un número distinto de "
                        "vectores que de fragmentos."
                    )
                for orden, (fragmento, vector) in enumerate(zip(fragmentos, vectores)):
                    nuevos_fragmentos.append(
                        ArticuloChunk(
                            portal_id=portal_id,
                            articulo_id=articulo_id,
                            idioma=traduccion.idioma,
                            orden=orden,
                            contenido=fragmento,
                            embedding=vector,
                        )
                    )
            # Reemplazo atómico: borra los anteriores y añade los nuevos en la
            # misma transacción. Si el commit falla, no queda el índice a medias.
            (
                db.query(ArticuloChunk)
                .filter(
                    ArticuloChunk.portal_id == portal_id,
                    ArticuloChunk.articulo_id == articulo_id,
                )
                .delete(synchronize_session=False)
            )
            for chunk in nuevos_fragmentos:
                db.add(chunk)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - captura defensiva del background
            logger.warning(
                "Re-embedido de artículo %s/%s falló: %s", portal_id, articulo_id, exc
            )
            db.rollback()


def borrar_fragmentos_articulo(portal_id: str, articulo_id: str) -> None:
    """Elimina los `articulo_chunks` de un artículo (llamada desde el borrado).

    No corre en background: es rápida (delete por índice) y sí ha de completarse
    antes de responder al cliente para cerrar el requisito «sin huérfanos». La
    cascada de la FK también los limpiaría al borrar el artículo, pero ejecutar
    el delete explícito lo hace observable en tests y desacopla del orden de
    borrado.
    """
    with _sesion() as db:
        (
            db.query(ArticuloChunk)
            .filter(
                ArticuloChunk.portal_id == portal_id,
                ArticuloChunk.articulo_id == articulo_id,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
