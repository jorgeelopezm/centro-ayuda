"""Comprobaciones HTTP que comparten los routers de administración.

Viven aquí, y no en `app.servicios`, para que la capa de servicios siga sin
depender de FastAPI: lo que se comparte es la traducción de un estado de la base
a un código de respuesta, que es asunto del router.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Articulo, Categoria, Documento


def obtener_articulo_o_404(db: Session, portal_id: str, articulo_id: str) -> Articulo:
    """Devuelve el artículo **del portal** o corta con 404.

    El filtro por `portal_id` es la barrera de aislamiento: pedir por id directo un
    artículo de otro portal responde 404 (inexistente) y no revela su existencia.
    """
    a = (
        db.query(Articulo)
        .filter(Articulo.id == articulo_id, Articulo.portal_id == portal_id)
        .first()
    )
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artículo no encontrado")
    return a


def exigir_id_disponible(db: Session, portal_id: str, articulo_id: str) -> None:
    """Corta con 409 si el portal ya tiene un artículo con ese identificador."""
    existe = (
        db.query(Articulo)
        .filter(Articulo.id == articulo_id, Articulo.portal_id == portal_id)
        .first()
    )
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un artículo con ese identificador")


def obtener_categoria_o_404(db: Session, portal_id: str, categoria_id: str) -> Categoria:
    """Devuelve la categoría **del portal** o corta con 404 (aislamiento por portal)."""
    c = (
        db.query(Categoria)
        .filter(Categoria.id == categoria_id, Categoria.portal_id == portal_id)
        .first()
    )
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada")
    return c


def exigir_categoria_id_disponible(db: Session, portal_id: str, categoria_id: str) -> None:
    """Corta con 409 si el portal ya tiene una categoría con ese identificador."""
    existe = (
        db.query(Categoria)
        .filter(Categoria.id == categoria_id, Categoria.portal_id == portal_id)
        .first()
    )
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una categoría con ese identificador")


def exigir_categoria_sin_articulos(db: Session, portal_id: str, categoria_id: str) -> None:
    """Corta con 409 si la categoría todavía tiene artículos asignados en el portal.

    Integridad referencial en la aplicación: el borrado nunca deja artículos sin
    categoría. La FK `articulos.categoria_id` no tiene cascada, así que esto refuerza
    a nivel de aplicación lo que la base ya impediría.
    """
    n = (
        db.query(Articulo)
        .filter(Articulo.categoria_id == categoria_id, Articulo.portal_id == portal_id)
        .count()
    )
    if n > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"No se puede borrar la categoría: tiene {n} artículo(s) asignado(s). "
            "Reasigna o elimina esos artículos primero.",
        )


def obtener_documento_o_404(db: Session, portal_id: str, documento_id: int) -> Documento:
    """Devuelve el documento **del portal** o corta con 404 (aislamiento por portal).

    Espeja el patrón de `obtener_articulo_o_404`: pedir por id directo un
    documento de otro portal responde 404 y no revela su existencia.
    """
    d = (
        db.query(Documento)
        .filter(Documento.id == documento_id, Documento.portal_id == portal_id)
        .first()
    )
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return d


def validar_relacionados(
    db: Session, portal_id: str, articulo_id: str, relacionados: Iterable[str]
) -> None:
    """Corta con 422 si algún relacionado es inválido.

    Un relacionado es inválido si es el propio artículo (auto-referencia) o si no
    corresponde a un artículo existente **del mismo portal** (no se enlaza contenido de
    otro portal). Se comprueba en el servidor para dar un error de validación claro en
    vez de un 500 por la FK (que además, al ser diferible, solo saltaría al commit)."""
    for rid in relacionados:
        if rid == articulo_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Un artículo no puede relacionarse consigo mismo: «{rid}».",
            )
        existe = (
            db.query(Articulo)
            .filter(Articulo.id == rid, Articulo.portal_id == portal_id)
            .first()
        )
        if existe is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"El artículo relacionado no existe: «{rid}».",
            )
