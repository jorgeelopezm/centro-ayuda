"""Tabla `sugerencia_articulo`: borrador de artículo por IA, pendiente de revisión
humana (spec `sugerencia-articulos-ia`).

Una fila por borrador. `contenido` guarda `{"es": {...}, "pt": {...}}` con la
forma que consume el formulario de artículo; `citas` es la lista de fragmentos
que lo sustentan, ya cruzados contra el portal. `(fuente, referencia)`
identifica el candidato de origen (agregado en `app.sugerencias`, no
persistido); sirve para no regenerar mientras exista una sugerencia
`pendiente` para el mismo candidato. `articulo_id` es `NULL` hasta aceptar
(sin FK: es informativa, no de integridad — `articulos` tiene PK compuesta por
portal y esta tabla nace después de la migración `0012_portal_uuid`, así que
`portal_id` ya es UUID desde el origen).

Índice `(portal_id, estado, creado_en desc)` para la cola de pendientes del
panel, agregada por portal y ordenada por fecha.

Reversible: `downgrade` dropea índice y tabla.

Revision ID: 0013_sugerencia_articulo
Revises: 0012_portal_uuid
Create Date: 2026-08-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0013_sugerencia_articulo"
down_revision: Union[str, Sequence[str], None] = "0012_portal_uuid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB en Postgres; JSON portable en el resto (coherente con `models.JsonType`).
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "sugerencia_articulo",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "portal_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("portales.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fuente", sa.String(), nullable=False),
        sa.Column("referencia", sa.String(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False, server_default="pendiente"),
        sa.Column("contenido", _JSON, nullable=False),
        sa.Column("citas", _JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("proveedor_chat", sa.String(), nullable=False),
        sa.Column("proveedor_traduccion", sa.String(), nullable=False),
        sa.Column("modelo", sa.String(), nullable=False),
        sa.Column("articulo_id", sa.String(), nullable=True),
        sa.Column("creado_por", sa.String(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
    )
    # Índice simple por portal (patrón `ix_{tabla}_portal_id` del resto del modelo).
    op.create_index(
        "ix_sugerencia_articulo_portal_id", "sugerencia_articulo", ["portal_id"]
    )
    # Índice de la cola de pendientes: por portal, estado y fecha reciente.
    op.create_index(
        "ix_sugerencia_articulo_portal_estado_creado",
        "sugerencia_articulo",
        ["portal_id", "estado", sa.text("creado_en DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_sugerencia_articulo_portal_estado_creado", table_name="sugerencia_articulo"
    )
    op.drop_index("ix_sugerencia_articulo_portal_id", table_name="sugerencia_articulo")
    op.drop_table("sugerencia_articulo")
