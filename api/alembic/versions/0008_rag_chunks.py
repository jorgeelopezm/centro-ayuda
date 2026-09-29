"""RAG: tablas `documentos`, `documento_chunks` y `articulo_chunks` con índice HNSW.

Da uso por primera vez a la extensión `vector` (pgvector) instalada en `0001`.
Introduce el esquema del pipeline de ingesta que hasta ahora solo estaba de
diseño (ADR-0001):

- `documentos`: metadatos del archivo subido en el panel (nombre, mime, idioma,
  estado del ciclo `pendiente|procesando|listo|error` y detalle de error). El
  binario no se persiste (design.md D7 del cambio `rag-ingesta`): se descarta
  tras extraer texto.
- `documento_chunks`: fragmento + `embedding vector(1536)`, con FK
  `documento_id` y `ON DELETE CASCADE` para que borrar un documento arrastre
  todos sus fragmentos.
- `articulo_chunks`: fragmento por **idioma** (`es|pt`) del contenido de
  artículos existentes, con `embedding vector(1536)`. La FK es **compuesta**
  `(portal_id, articulo_id) → articulos(portal_id, id)` porque la PK de
  `articulos` es compuesta desde `0006`; también `CASCADE`.

Todas las tablas llevan `portal_id` (FK a `portales`, `index`) para aislar el
RAG por tenant. Sobre cada `embedding` se crea un índice **HNSW**
(`vector_cosine_ops`): mejor recall/latencia que IVFFlat sin necesidad de
reentreno periódico. Se crea aunque `/buscar` aún no exista, para que la tabla
nazca lista.

La dimensión `1536` corresponde a `text-embedding-3-small` de OpenAI (decisión
del cambio `rag-ingesta`; ver `app.rag.EMBEDDING_DIM`, constante única).
Cambiar de modelo implica cambiar la constante, migrar el esquema y re-embeber
todo el contenido (no soportado como migración automática).

Es reversible: `downgrade` retira las tres tablas y sus índices; nada del resto
del sistema depende aún de ellas (la recuperación no se ha cableado), así que
revertir no afecta al chat prototipo ni al contenido.

Revision ID: 0008_rag_chunks
Revises: 0007_empresa_en_portal
Create Date: 2026-08-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.rag import EMBEDDING_DIM

revision: str = "0008_rag_chunks"
down_revision: Union[str, Sequence[str], None] = "0007_empresa_en_portal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `documentos`: metadatos del archivo. `bytes` es informativo (tamaño del
    # original) para que el panel pueda mostrarlo si hace falta; el binario se
    # descarta. El estado nace en `pendiente`; la ingesta lo mueve a
    # `procesando` y luego a `listo` o `error`.
    op.create_table(
        "documentos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portal_id", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("mime", sa.String(), nullable=False),
        sa.Column("idioma", sa.String(), nullable=False, server_default="ambos"),
        sa.Column("estado", sa.String(), nullable=False, server_default="pendiente"),
        sa.Column("error_detalle", sa.String(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["portal_id"], ["portales.id"], name="fk_documentos_portal"),
    )
    op.create_index("ix_documentos_portal_id", "documentos", ["portal_id"])

    # `documento_chunks`: fragmento + embedding. CASCADE al padre para no dejar
    # huérfanos al borrar el documento.
    op.create_table(
        "documento_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portal_id", sa.String(), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.ForeignKeyConstraint(
            ["portal_id"], ["portales.id"], name="fk_documento_chunks_portal"
        ),
        sa.ForeignKeyConstraint(
            ["documento_id"],
            ["documentos.id"],
            name="fk_documento_chunks_documento",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_documento_chunks_portal_id", "documento_chunks", ["portal_id"])
    op.create_index(
        "ix_documento_chunks_documento_id", "documento_chunks", ["documento_id"]
    )
    # HNSW por coseno: alternativa IVFFlat descartada (exige `ANALYZE`/reentreno
    # de listas). Se crea aunque la recuperación aún no exista para que las
    # tablas nazcan listas.
    op.execute(
        "CREATE INDEX ix_documento_chunks_embedding_hnsw "
        "ON documento_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    # `articulo_chunks`: FK compuesta a `articulos(portal_id, id)`. Índice por
    # `(portal_id, articulo_id)` para acelerar el re-embedido (borrar y
    # reinsertar los fragmentos de un artículo).
    op.create_table(
        "articulo_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("portal_id", sa.String(), nullable=False),
        sa.Column("articulo_id", sa.String(), nullable=False),
        sa.Column("idioma", sa.String(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.ForeignKeyConstraint(
            ["portal_id"], ["portales.id"], name="fk_articulo_chunks_portal"
        ),
        sa.ForeignKeyConstraint(
            ["portal_id", "articulo_id"],
            ["articulos.portal_id", "articulos.id"],
            name="fk_articulo_chunks_articulo",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_articulo_chunks_portal_id", "articulo_chunks", ["portal_id"])
    op.create_index(
        "ix_articulo_chunks_articulo",
        "articulo_chunks",
        ["portal_id", "articulo_id"],
    )
    op.execute(
        "CREATE INDEX ix_articulo_chunks_embedding_hnsw "
        "ON articulo_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    # `articulo_chunks` primero: no depende de `documentos`, y sus índices se
    # sueltan explícitamente por si el motor no los arrastra al DROP TABLE.
    op.execute("DROP INDEX IF EXISTS ix_articulo_chunks_embedding_hnsw")
    op.drop_index("ix_articulo_chunks_articulo", table_name="articulo_chunks")
    op.drop_index("ix_articulo_chunks_portal_id", table_name="articulo_chunks")
    op.drop_table("articulo_chunks")

    op.execute("DROP INDEX IF EXISTS ix_documento_chunks_embedding_hnsw")
    op.drop_index("ix_documento_chunks_documento_id", table_name="documento_chunks")
    op.drop_index("ix_documento_chunks_portal_id", table_name="documento_chunks")
    op.drop_table("documento_chunks")

    op.drop_index("ix_documentos_portal_id", table_name="documentos")
    op.drop_table("documentos")
    # La extensión `vector` se deja instalada: la creó `0001` y otras cosas
    # (o migraciones futuras) podrían depender de ella.
