"""Integridad referencial de `articulo_relacionados.relacionado_id`.

Hasta ahora solo `articulo_id` tenía clave foránea; `relacionado_id` era texto
libre, así que borrar un artículo dejaba colgando los enlaces que lo apuntaban
(sus enlaces *entrantes*). Esta migración limpia cualquier enlace colgante y
añade la FK `relacionado_id -> articulos.id` con `ON DELETE CASCADE`, declarada
**DEFERRABLE INITIALLY DEFERRED**: el aplazamiento al commit permite que sigan
funcionando las referencias mutuas y los ciclos del seed (p. ej.
`direccion-envio` <-> `seguimiento-pedido`), que una FK inmediata rompería.

Es incremental sobre `0004`. El `DELETE` previo hace la creación de la FK segura
e idempotente en cualquier entorno.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-10
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT = "fk_articulo_relacionados_relacionado_id"


def upgrade() -> None:
    # Elimina enlaces que apuntan a un artículo inexistente antes de crear la FK.
    op.execute(
        "DELETE FROM articulo_relacionados r "
        "WHERE NOT EXISTS (SELECT 1 FROM articulos a WHERE a.id = r.relacionado_id)"
    )
    op.create_foreign_key(
        CONSTRAINT,
        source_table="articulo_relacionados",
        referent_table="articulos",
        local_cols=["relacionado_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT, "articulo_relacionados", type_="foreignkey")
