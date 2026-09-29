"""Chat con RAG: campos opcionales de modelo y temperatura en `config_ia`.

Añade `modelo_chat` y `temperatura_chat` a la fila singleton `config_ia` para
que SuperAdmin pueda ajustar el modelo de chat y su temperatura sin desplegar
código, sin tocar el proveedor de embeddings (Voyage) ni el de traducción.

Ambos son nullable a propósito: `None` deja que el pipeline caiga a los valores
por defecto codificados (`deepseek-chat`, 0.2). No hay cambios en
`articulo_chunks` ni en `documento_chunks`: la recuperación reusa el esquema
existente del cambio `rag-ingesta` (migración `0008_rag_chunks`).

Es reversible: `downgrade` retira ambas columnas.

Revision ID: 0009_chat_rag_config
Revises: 0008_rag_chunks
Create Date: 2026-08-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_chat_rag_config"
down_revision: Union[str, Sequence[str], None] = "0008_rag_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("config_ia", sa.Column("modelo_chat", sa.String(), nullable=True))
    op.add_column("config_ia", sa.Column("temperatura_chat", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("config_ia", "temperatura_chat")
    op.drop_column("config_ia", "modelo_chat")
