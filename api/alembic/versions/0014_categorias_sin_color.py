"""Elimina `fondo`/`texto` de `categorias` (cambio `mejorar-panel-categorias`).

La presentación visual de las tarjetas de categoría deja de ser un color libre
por categoría (clases Tailwind escritas a mano, sin relación con el acento del
portal) y pasa a derivarse siempre de `--acento-claro`/`--acento` del portal
resuelto, el mismo patrón que ya usan las tarjetas KPI del panel. No toca
`nombre`, `slug`, `icono`, `orden` ni las asignaciones de artículo a categoría.

Reversible: `downgrade` restituye las dos columnas con los valores por defecto
que tenía el modelo antes de este cambio (aspecto índigo), no los colores
originales por categoría (esos se pierden al hacer `upgrade`).

Revision ID: 0014_categorias_sin_color
Revises: 0013_sugerencia_articulo
Create Date: 2026-08-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_categorias_sin_color"
down_revision: Union[str, Sequence[str], None] = "0013_sugerencia_articulo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("categorias", "fondo")
    op.drop_column("categorias", "texto")


def downgrade() -> None:
    op.add_column(
        "categorias",
        sa.Column("texto", sa.String(), nullable=False, server_default="text-indigo-700"),
    )
    op.add_column(
        "categorias",
        sa.Column("fondo", sa.String(), nullable=False, server_default="bg-indigo-50"),
    )
