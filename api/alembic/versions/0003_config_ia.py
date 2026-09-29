"""Configuración de proveedor de IA (singleton).

Crea la tabla `config_ia` (fila única `id=1`) con el proveedor activo y un mapa
JSON de claves de API cifradas por proveedor. Es incremental sobre `0002`: no toca
las tablas existentes. La fila la crea/actualiza el panel (Administrador); si no existe, el
proveedor efectivo por defecto es Anthropic (Claude).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB en Postgres; JSON portable en el resto (coherente con models.JsonType).
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "config_ia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proveedor_activo", sa.String(), nullable=False, server_default="anthropic"),
        sa.Column("claves", _JSON, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("config_ia")
