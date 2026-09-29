"""El nombre de empresa se consolida en `portales.nombre_empresa` y se retira de `ajustes`.

El valor de marca `[Empresa]` tenía dos sedes: `ajustes.empresa` (editable) y
`portales.nombre_empresa` (fijado al crear el portal). La spec `gestion-portales` pide
que el nombre venga del portal, así que se deja **una sola fuente**: `portales.nombre_empresa`.
Antes de eliminar la columna se sincroniza por seguridad (la `0006` ya había volcado el
valor del portal `default` desde `ajustes`, así que en la práctica es un no-op defensivo).

Es reversible: `downgrade` re-crea `ajustes.empresa` y la rellena desde el portal.

Revision ID: 0007_empresa_en_portal
Revises: 0006_portales
Create Date: 2026-08-16
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_empresa_en_portal"
down_revision: Union[str, Sequence[str], None] = "0006_portales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Sincroniza el nombre de empresa hacia `portales` por si alguna fila quedó sin él
    # (la `0006` ya lo volcó para `default`; aquí solo se cubren huecos residuales).
    bind.execute(
        sa.text(
            "UPDATE portales SET nombre_empresa = a.empresa "
            "FROM ajustes a WHERE a.portal_id = portales.id "
            "AND (portales.nombre_empresa IS NULL OR portales.nombre_empresa = '')"
        )
    )
    op.drop_column("ajustes", "empresa")


def downgrade() -> None:
    # Se re-crea nullable, se rellena desde el portal y luego se impone NOT NULL, el
    # patrón seguro para reintroducir una columna obligatoria sin perder datos.
    op.add_column("ajustes", sa.Column("empresa", sa.String(), nullable=True))
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE ajustes SET empresa = p.nombre_empresa "
            "FROM portales p WHERE p.id = ajustes.portal_id"
        )
    )
    op.alter_column("ajustes", "empresa", nullable=False)
