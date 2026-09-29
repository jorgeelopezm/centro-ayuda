"""Esquema inicial: extensión pgvector y tablas del centro de ayuda.

Revision ID: 0001
Revises:
Create Date: 2026-07-28
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # RAG-ready: la extensión queda disponible desde el inicio (aún no se usa).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "categorias",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("icono", sa.String(), nullable=False),
        sa.Column("fondo", sa.String(), nullable=False),
        sa.Column("texto", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "categoria_traducciones",
        sa.Column("categoria_id", sa.String(), sa.ForeignKey("categorias.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("idioma", sa.String(), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
    )
    op.create_table(
        "articulos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("categoria_id", sa.String(), sa.ForeignKey("categorias.id"), nullable=False),
        sa.Column("actualizado", sa.Date(), nullable=False),
        sa.Column("minutos_lectura", sa.Integer(), nullable=False),
        sa.Column("destacado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "articulo_traducciones",
        sa.Column("articulo_id", sa.String(), sa.ForeignKey("articulos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("idioma", sa.String(), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("parrafos", postgresql.JSONB(), nullable=False),
        sa.Column("how_to", postgresql.JSONB(), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        sa.Column("faq", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "articulo_relacionados",
        sa.Column("articulo_id", sa.String(), sa.ForeignKey("articulos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("relacionado_id", sa.String(), primary_key=True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "preguntas_sin_resolver",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("idioma", sa.String(), nullable=False),
        sa.Column("pregunta", sa.String(), nullable=False),
        sa.Column("veces", sa.Integer(), nullable=False),
        sa.Column("similitud", sa.Float(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "conversaciones",
        sa.Column("idioma", sa.String(), primary_key=True),
        sa.Column("mensajes", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "metricas",
        sa.Column("idioma", sa.String(), primary_key=True),
        sa.Column("clave", sa.String(), primary_key=True),
        sa.Column("valor", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.drop_table("admin_users")
    op.drop_table("metricas")
    op.drop_table("conversaciones")
    op.drop_table("preguntas_sin_resolver")
    op.drop_table("articulo_relacionados")
    op.drop_table("articulo_traducciones")
    op.drop_table("articulos")
    op.drop_table("categoria_traducciones")
    op.drop_table("categorias")
    # La extensión vector se deja instalada (puede usarla otro esquema).
