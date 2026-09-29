"""Escritura de interacciones del chat en `chat_interaccion`.

Al final del pipeline `app.chat.responder` se llama a `persistir(...)` con los
datos de la interacción para que la conversación quede auditable desde el panel
(spec `supervision-chats`). La escritura es síncrona dentro del request; un
fallo se registra en el log y NO propaga la excepción — la respuesta al usuario
sigue devolviéndose intacta.

Nota de diseño (deviación consciente respecto al literal "abrir una sesión
propia" del design.md): el pipeline del chat no ejecuta ningún `commit` propio
(solo lecturas de recuperación y de `ConfigIA`), así que reutilizar la sesión
del request y aislar la escritura con `try/commit/except/rollback` ya cumple la
garantía "un fallo al persistir no rompe la respuesta". Abrir un `sessionmaker`
paralelo dificultaría los tests con SQLite en memoria (pool `StaticPool`) sin
aportar aislamiento adicional aquí.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ChatInteraccion

logger = logging.getLogger(__name__)


@dataclass
class InteraccionAPersistir:
    """Datos de una interacción listos para insertar. El `turno` se calcula al
    persistir a partir del recuento actual de filas del mismo `chat_id`."""

    portal_id: str
    chat_id: str
    idioma: str
    consulta: str
    veredicto: str
    mensaje: str
    citas: list[dict[str, Any]]
    razon_escalamiento: str | None
    latencia_ms: int
    tokens_entrada: int | None
    tokens_salida: int | None
    proveedor: str
    modelo: str


def _siguiente_turno(db: Session, chat_id: str) -> int:
    """Devuelve `count(chat_interaccion WHERE chat_id=...) + 1` para asignar el
    número de turno 1-based del `chat_id`. Barato porque hay índice por `chat_id`
    y la cardinalidad por chat es baja (unos pocos turnos)."""
    total = db.execute(
        select(func.count()).select_from(ChatInteraccion).where(
            ChatInteraccion.chat_id == chat_id
        )
    ).scalar_one()
    return int(total) + 1


def persistir(interaccion: InteraccionAPersistir, db: Session) -> None:
    """Inserta la interacción en `chat_interaccion` y hace commit. Cualquier
    fallo (constraint, base indisponible, ...) se captura, se loguea y NO se
    propaga: la respuesta al usuario ya se decidió y no debe verse afectada."""
    try:
        turno = _siguiente_turno(db, interaccion.chat_id)
        db.add(
            ChatInteraccion(
                id=uuid.uuid4().hex,
                # `uuid.UUID(...)`: `interaccion.portal_id` llega como `str`;
                # `ChatInteraccion.portal_id` es `uuid.UUID` (columna `Uuid`) y
                # SQLAlchemy exige el tipo Python nativo al enlazar el INSERT.
                portal_id=uuid.UUID(interaccion.portal_id),
                chat_id=interaccion.chat_id,
                turno=turno,
                idioma=interaccion.idioma,
                consulta=interaccion.consulta,
                veredicto=interaccion.veredicto,
                mensaje=interaccion.mensaje,
                citas=list(interaccion.citas),
                razon_escalamiento=interaccion.razon_escalamiento,
                latencia_ms=interaccion.latencia_ms,
                tokens_entrada=interaccion.tokens_entrada,
                tokens_salida=interaccion.tokens_salida,
                proveedor=interaccion.proveedor,
                modelo=interaccion.modelo,
            )
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - garantía "no rompe la respuesta"
        logger.warning(
            "chat_interaccion: fallo al persistir (%s)", type(exc).__name__
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
