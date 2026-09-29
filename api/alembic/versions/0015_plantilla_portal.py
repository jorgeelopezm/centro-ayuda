"""Plantilla del centro de ayuda por portal (cambio `plantillas-centro-ayuda`).

Añade a `ajustes` la columna `plantilla`, con la plantilla `default` como valor por
defecto. Es aditiva: ninguna fila ni tabla existente se reescribe, así que todos los
portales existentes conservan el aspecto actual hasta que un Administrador elija la
otra plantilla a propósito. El conjunto de valores admitidos y el normalizador de
lectura viven en `app/servicios.py` (fuente única); la columna es texto y no un tipo
enumerado para poder admitir una plantilla futura sin `ALTER TYPE`.

Reversible: `downgrade` elimina la columna (y con ella la elección guardada).

Revision ID: 0015_plantilla_portal
Revises: 0014_categorias_sin_color
Create Date: 2026-09-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_plantilla_portal"
down_revision: Union[str, Sequence[str], None] = "0014_categorias_sin_color"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ajustes",
        sa.Column("plantilla", sa.String(), nullable=False, server_default="default"),
    )


def downgrade() -> None:
    op.drop_column("ajustes", "plantilla")
