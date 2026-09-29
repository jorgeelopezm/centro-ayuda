"""Refresh tokens opacos de sesión (rotación con detección de reutilización).

Crea la tabla `refresh_tokens`, que guarda el **hash** de cada refresh token (no
el valor en claro), su familia de rotación, expiración y banderas `usado`/
`revocado`. Es incremental sobre `0003`: no toca tablas existentes. La usa el BFF
de Next para renovar el access token en silencio; ver `app.sesiones`.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "admin_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("familia", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column(
            "emitido",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expira", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revocado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_refresh_tokens_admin_id", "refresh_tokens", ["admin_id"])
    op.create_index("ix_refresh_tokens_familia", "refresh_tokens", ["familia"])
    op.create_index(
        "ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_familia", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_admin_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
