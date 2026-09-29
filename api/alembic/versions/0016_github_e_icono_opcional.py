"""Enlace de GitHub por portal e icono de categoría opcional.

Dos cambios aditivos de presentación:

- `ajustes.github_url`: URL opcional del repositorio del portal. La plantilla de
  documentación muestra el icono de GitHub en la cabecera solo si está fijada; nula en
  todos los portales existentes, así que ninguno cambia de aspecto hasta que un
  Administrador la guarde.
- `categorias.icono` pasa a admitir nulo («sin icono»). Las filas existentes conservan
  su icono; el conjunto admitido sigue validándose en `IconoCategoria` (`schemas.py`).

Reversible: `downgrade` elimina la columna y, antes de volver a exigir el icono, rellena
con `documento` las categorías que se quedaron sin él (si no, el `NOT NULL` fallaría).

Revision ID: 0016_github_e_icono_opcional
Revises: 0015_plantilla_portal
Create Date: 2026-09-29
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_github_e_icono_opcional"
down_revision: Union[str, Sequence[str], None] = "0015_plantilla_portal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ajustes", sa.Column("github_url", sa.String(), nullable=True))
    with op.batch_alter_table("categorias") as tabla:
        tabla.alter_column("icono", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE categorias SET icono = 'documento' WHERE icono IS NULL")
    with op.batch_alter_table("categorias") as tabla:
        tabla.alter_column("icono", existing_type=sa.String(), nullable=False)
    op.drop_column("ajustes", "github_url")
