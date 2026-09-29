"""Niveles de acceso (Editor/Administrador), estado activo y campo [Empresa].

Añade a `admin_users` las columnas `nivel` y `activo`, y crea la tabla singleton
`ajustes` con el campo [Empresa]. Es una migración incremental sobre `0001` para
que una base ya migrada gane las columnas sin recrearse.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nuevas filas: Editor por defecto (el nivel más bajo con sesión), para no
    # otorgar Administrador por omisión. `activo=true` por defecto.
    op.add_column("admin_users", sa.Column("nivel", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("admin_users", sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()))

    # Los administradores que ya existían son anteriores a los niveles y tenían
    # acceso total: se promueven a Administrador para no dejar la instalación sin Administrador.
    # En una base nueva no hay filas todavía (el seed corre después), así que no
    # afecta nada; el seed crea el admin inicial como Administrador explícitamente.
    op.execute("UPDATE admin_users SET nivel = 3")

    # Ajustes globales (singleton): el campo [Empresa]. La fila la crea el seed.
    op.create_table(
        "ajustes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("empresa", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ajustes")
    op.drop_column("admin_users", "activo")
    op.drop_column("admin_users", "nivel")
