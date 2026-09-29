"""Poblado inicial (o re-embedido total) del índice de `articulo_chunks`.

Recorre todos los portales y todos sus artículos, y regenera los fragmentos e
embeddings. Es **idempotente**: cada artículo se procesa con
`ingesta.reindexar_articulo`, que borra los fragmentos anteriores del artículo
antes de insertar los nuevos, así que volver a correrlo no duplica nada ni deja
huérfanos.

Uso previsto:

1. Tras aplicar la migración `0008_rag_chunks`, para llenar el índice con los
   artículos que ya existen (el hook automático de `admin_articulos.py` solo
   cubre altas y ediciones nuevas).
2. Como operación de mantenimiento si se cambia el modelo de embeddings
   (`EMBEDDING_DIM`) — hay que migrar el esquema y re-embeber todo.

Requiere que exista una clave OpenAI en `ConfigIA` (SuperAdmin la introduce por
el panel de IA); si no, cada llamada al embedder falla con
`ProveedorNoConfigurado` y el artículo queda con los fragmentos previos (o sin
ninguno si era la primera vez). No revienta el proceso: registra el error y
sigue con el siguiente artículo.

Ejecución (desde `api/`, con el entorno virtual y la base de datos activos):

    python reindexar_articulos.py
"""

from __future__ import annotations

import logging
import sys

from app.database import SessionLocal
from app.ingesta import reindexar_articulo
from app.models import Articulo, Portal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
)
logger = logging.getLogger("reindexar-articulos")


def reindexar_todos() -> int:
    """Reindexa todos los artículos de todos los portales. Devuelve el nº procesado."""
    procesados = 0
    with SessionLocal() as db:
        portales = db.query(Portal).order_by(Portal.id).all()
        for portal in portales:
            articulos = (
                db.query(Articulo)
                .filter(Articulo.portal_id == portal.id)
                .order_by(Articulo.orden)
                .all()
            )
            logger.info(
                "Portal %s (%s): %d artículo(s) a reindexar",
                portal.id, portal.slug, len(articulos),
            )
            for articulo in articulos:
                try:
                    reindexar_articulo(portal.id, articulo.id)
                    procesados += 1
                    logger.info("  ✓ %s", articulo.id)
                except Exception as exc:  # noqa: BLE001 - no queremos abortar
                    logger.warning("  ✗ %s: %s", articulo.id, exc)
    return procesados


if __name__ == "__main__":
    total = reindexar_todos()
    logger.info("Reindexado terminado: %d artículo(s) procesado(s).", total)
    sys.exit(0)
