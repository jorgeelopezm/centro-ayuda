"""Marca visual en `ajustes`: color de acento, degradado del banner y logotipo.

Añade a la fila única de `ajustes` las columnas de acento (`acento`), las tres
paradas del degradado del banner (`banner_desde`/`banner_medio`/`banner_hasta`) y el
logotipo (`logo_bin` + `logo_mime`). Es incremental sobre `0004`: no toca tablas
existentes. Los colores llevan `server_default` = aspecto índigo actual, de modo que
las instalaciones existentes conservan su apariencia; el logo nace nulo.

Revision ID: 0005_marca
Revises: 0004
Create Date: 2026-08-12

Nota: el id es `0005_marca` (no `0005`) a propósito. La rama `integridad-relacionados-fk`
añadió otra migración con id `0005`; usar un id distinto evita que Alembic las confunda
(una base sellada con `0005` daría por aplicada la que no es). Al fusionar ambas ramas
quedarán dos hijos de `0004`: resuélvelo con `alembic merge heads`.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_marca"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ajustes",
        sa.Column("acento", sa.String(), nullable=False, server_default="#4338ca"),
    )
    op.add_column(
        "ajustes",
        sa.Column("banner_desde", sa.String(), nullable=False, server_default="#3730a3"),
    )
    op.add_column(
        "ajustes",
        sa.Column("banner_medio", sa.String(), nullable=False, server_default="#4338ca"),
    )
    op.add_column(
        "ajustes",
        sa.Column("banner_hasta", sa.String(), nullable=False, server_default="#4f46e5"),
    )
    op.add_column("ajustes", sa.Column("logo_bin", sa.LargeBinary(), nullable=True))
    op.add_column("ajustes", sa.Column("logo_mime", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("ajustes", "logo_mime")
    op.drop_column("ajustes", "logo_bin")
    op.drop_column("ajustes", "banner_hasta")
    op.drop_column("ajustes", "banner_medio")
    op.drop_column("ajustes", "banner_desde")
    op.drop_column("ajustes", "acento")
