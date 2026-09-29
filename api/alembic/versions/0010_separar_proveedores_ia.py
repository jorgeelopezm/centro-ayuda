"""Separación de proveedores de IA por rol (chat / traducción / embeddings).

Sustituye la fila singleton `config_ia` que hoy tiene un único `proveedor_activo`
y un dict JSONB `claves` por tres campos escalares (uno por rol) y una tabla
dedicada `config_ia_clave` (una fila por proveedor con su token cifrado).

Reversible: `downgrade` reconstruye `proveedor_activo` desde el rol de chat (o el
de traducción, o el default `anthropic`) y vuelve a poblar el JSONB `claves` con
las filas de `config_ia_clave` antes de dropearla. Ver cambio OpenSpec
`separar-proveedores-ia`.

Revision ID: 0010_separar_proveedores_ia
Revises: 0009_chat_rag_config
Create Date: 2026-08-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010_separar_proveedores_ia"
down_revision: Union[str, Sequence[str], None] = "0009_chat_rag_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# JSONB en Postgres; JSON portable en el resto (coherente con `0003_config_ia`).
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")

# Proveedores que sobreviven al recorte de este cambio (ver design.md D9: `google`
# se retira del `Literal ProveedorIA` porque no tiene motor real). Cualquier
# entrada del JSONB con otro nombre se descarta en el upgrade — no era un
# proveedor válido.
_PROVEEDORES_ADMITIDOS = {"anthropic", "deepseek", "openai", "voyage"}


def upgrade() -> None:
    # 1) Nueva tabla `config_ia_clave` (una fila por proveedor).
    op.create_table(
        "config_ia_clave",
        sa.Column("proveedor", sa.String(), primary_key=True),
        sa.Column("token_cifrado", sa.Text(), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # 2) Tres columnas nuevas en `config_ia`, todas NULL por defecto: la fábrica
    #    de cada rol cae a su default codificado cuando el campo es NULL.
    op.add_column("config_ia", sa.Column("proveedor_chat", sa.String(), nullable=True))
    op.add_column("config_ia", sa.Column("proveedor_traduccion", sa.String(), nullable=True))
    op.add_column("config_ia", sa.Column("proveedor_embeddings", sa.String(), nullable=True))

    # 3) Migrar los datos existentes: por cada fila de `config_ia`, copiar el
    #    `proveedor_activo` a chat y traducción (así el comportamiento antiguo
    #    "un solo proveedor activo" se conserva para esos dos roles). Para
    #    embeddings, si la instalación ya guardaba una clave `voyage`, dejarlo
    #    como embeddings por defecto; en otro caso NULL (default codificado).
    conn = op.get_bind()
    filas = conn.execute(sa.text("SELECT id, proveedor_activo, claves FROM config_ia")).fetchall()
    for fila in filas:
        fila_id = fila[0]
        proveedor_activo = fila[1]
        claves = fila[2] or {}
        proveedor_embeddings = "voyage" if claves.get("voyage") else None
        conn.execute(
            sa.text(
                "UPDATE config_ia SET proveedor_chat=:chat, "
                "proveedor_traduccion=:trad, proveedor_embeddings=:emb WHERE id=:id"
            ),
            {
                "chat": proveedor_activo,
                "trad": proveedor_activo,
                "emb": proveedor_embeddings,
                "id": fila_id,
            },
        )
        # Migrar el dict de claves a filas de `config_ia_clave`, descartando
        # cualquier proveedor no admitido (p. ej. `google`, sin motor real).
        for proveedor, token in claves.items():
            if not token or proveedor not in _PROVEEDORES_ADMITIDOS:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO config_ia_clave (proveedor, token_cifrado) "
                    "VALUES (:proveedor, :token)"
                ),
                {"proveedor": proveedor, "token": token},
            )

    # 4) Dropear las columnas viejas ya que sus datos están en el nuevo esquema.
    op.drop_column("config_ia", "claves")
    op.drop_column("config_ia", "proveedor_activo")


def downgrade() -> None:
    # 1) Recrear las columnas viejas en `config_ia`. `proveedor_activo` es NOT NULL
    #    con default `anthropic` (mismo default de `0003`); `claves` es NOT NULL
    #    con default `{}`.
    op.add_column(
        "config_ia",
        sa.Column(
            "proveedor_activo",
            sa.String(),
            nullable=False,
            server_default="anthropic",
        ),
    )
    op.add_column(
        "config_ia",
        sa.Column("claves", _JSON, nullable=False, server_default="{}"),
    )

    # 2) Poblar `proveedor_activo` a partir del chat (o traducción como fallback).
    #    Y reconstruir el dict `claves` desde las filas de `config_ia_clave`.
    conn = op.get_bind()
    claves_por_proveedor: dict[str, str] = {}
    for proveedor, token in conn.execute(
        sa.text("SELECT proveedor, token_cifrado FROM config_ia_clave")
    ).fetchall():
        claves_por_proveedor[proveedor] = token

    filas = conn.execute(
        sa.text("SELECT id, proveedor_chat, proveedor_traduccion FROM config_ia")
    ).fetchall()
    for fila_id, prov_chat, prov_trad in filas:
        activo = prov_chat or prov_trad or "anthropic"
        # `bindparam(..., type_=_JSON)` sirve para SQLite; en Postgres el JSONB
        # acepta el dict directamente.
        conn.execute(
            sa.text("UPDATE config_ia SET proveedor_activo=:activo, claves=:claves WHERE id=:id").bindparams(
                sa.bindparam("claves", type_=_JSON)
            ),
            {"activo": activo, "claves": claves_por_proveedor, "id": fila_id},
        )

    # 3) Dropear la tabla y las columnas nuevas.
    op.drop_column("config_ia", "proveedor_embeddings")
    op.drop_column("config_ia", "proveedor_traduccion")
    op.drop_column("config_ia", "proveedor_chat")
    op.drop_table("config_ia_clave")
