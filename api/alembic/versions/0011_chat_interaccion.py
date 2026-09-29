"""Tabla `chat_interaccion`: traza persistente del chat con RAG por portal.

Una fila por turno del chat. `chat_id` es opaco (alias del `session_id` del
pipeline) y se repite por cada turno; `turno` es 1-based dentro del `chat_id`.
Sirve al panel de supervisión (spec `supervision-chats`) y al harness de eval.

Índices: `(portal_id, creado_en desc)` para el listado agregado del panel;
`(chat_id)` para el detalle. `citas` es JSONB en Postgres (JSON portable en
SQLite para tests, coherente con `documento_chunks` y compañía).

Reversible: `downgrade` dropea índices y tabla.

Revision ID: 0011_chat_interaccion
Revises: 0010_separar_proveedores_ia
Create Date: 2026-08-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011_chat_interaccion"
down_revision: Union[str, Sequence[str], None] = "0010_separar_proveedores_ia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB en Postgres; JSON portable en el resto (coherente con `models.JsonType`).
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "chat_interaccion",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "portal_id",
            sa.String(),
            sa.ForeignKey("portales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("turno", sa.Integer(), nullable=False),
        sa.Column("idioma", sa.String(), nullable=False),
        sa.Column("consulta", sa.Text(), nullable=False),
        sa.Column("veredicto", sa.String(), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("citas", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("razon_escalamiento", sa.String(), nullable=True),
        sa.Column("latencia_ms", sa.Integer(), nullable=False),
        sa.Column("tokens_entrada", sa.Integer(), nullable=True),
        sa.Column("tokens_salida", sa.Integer(), nullable=True),
        sa.Column("proveedor", sa.String(), nullable=False),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Índice para el listado agregado del panel: por portal y actividad reciente.
    op.create_index(
        "ix_chat_interaccion_portal_creado",
        "chat_interaccion",
        ["portal_id", sa.text("creado_en DESC")],
    )
    # Índice para el detalle: todas las interacciones de un `chat_id` en orden.
    op.create_index(
        "ix_chat_interaccion_chat_id",
        "chat_interaccion",
        ["chat_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_interaccion_chat_id", table_name="chat_interaccion")
    op.drop_index("ix_chat_interaccion_portal_creado", table_name="chat_interaccion")
    op.drop_table("chat_interaccion")
