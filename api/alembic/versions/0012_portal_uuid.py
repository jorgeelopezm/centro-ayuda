"""`portales.id` pasa de `String` (hoy `id == slug`) a `UUID` opaco.

Separa identidad de nombre público: `id` es ahora un UUID interno, inmutable,
generado por la aplicación (`uuid.uuid4()` en `Portal.id`, ver `models.py`);
`slug` sigue siendo la columna `UNIQUE` legible que define el subdominio y
queda libre para hacerse editable en un cambio futuro sin cascadear ninguna
FK. `platform` (ver `PORTAL_PLATAFORMA_SLUG`) y `default`
(`PORTAL_DEFECTO_SLUG`) reciben UUIDs **fijos** —los mismos que
`app.servicios.PORTAL_DEFECTO_UUID` / `PORTAL_PLATAFORMA_UUID`— para que una
base ya sembrada (por el seed o por `0006_portales`/`0007`) no quede
huérfana: el seed es idempotente por `db.get(Portal, PORTAL_DEFECTO_UUID)`, y
si el backfill les diera un UUID aleatorio, un re-seed intentaría crear un
portal `default`/`platform` duplicado (choque de `slug` UNIQUE). El resto de
portales (creados desde el panel) recibe un UUID aleatorio (`gen_random_uuid()`,
disponible en el core de Postgres desde la 13, sin necesitar `pgcrypto`; el
`pgvector/pgvector:pg16` de `docker-compose.yml` ya lo trae).

Toca las 14 tablas con `portal_id: String → portales.id` (`dominios`,
`categorias`, `categoria_traducciones`, `articulos`, `articulo_traducciones`,
`preguntas_sin_resolver`, `conversaciones`, `metricas`, `admin_users`,
`ajustes`, `documentos`, `documento_chunks`, `articulo_chunks`,
`chat_interaccion`) más `articulo_relacionados` (tiene `portal_id` pero sin FK
simple propia a `portales`, solo las compuestas hacia `articulos`) — 15 en
total. Patrón por tabla, igual que `0006_portales`: añadir `portal_id_nuevo
UUID` nullable → *backfill* por join contra `portales` → `NOT NULL` → soltar
lo viejo → renombrar. El orden importa: primero se sueltan las FKs/PKs/
uniques que dependen del tipo `String` (empezando por las compuestas
hijas-de-`articulos`/`categorias`, luego las FKs simples a `portales.id`,
luego las PKs y uniques), después se cambian las columnas, y al final se
reconstruye todo con el tipo `UUID`.

Reversible: `downgrade` vuelve a `String`, con el `id` de cada portal
backfilleado a su `slug` (el invariante `id == slug` que tenía antes de esta
migración).

Revision ID: 0012_portal_uuid
Revises: 0011_chat_interaccion
Create Date: 2026-08-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0012_portal_uuid"
down_revision: Union[str, Sequence[str], None] = "0011_chat_interaccion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Espejo de `app.servicios.PORTAL_DEFECTO_UUID` / `PORTAL_PLATAFORMA_UUID`.
PORTAL_DEFECTO_SLUG = "default"
PORTAL_DEFECTO_UUID = "00000000-0000-0000-0000-000000000001"
PORTAL_PLATAFORMA_SLUG = "platform"
PORTAL_PLATAFORMA_UUID = "00000000-0000-0000-0000-000000000002"

# Las 15 tablas con columna `portal_id` (todas menos `portales`, que tiene el `id`).
_TABLAS_PORTAL_ID = (
    "dominios",
    "categorias",
    "categoria_traducciones",
    "articulos",
    "articulo_traducciones",
    "articulo_relacionados",
    "preguntas_sin_resolver",
    "conversaciones",
    "metricas",
    "admin_users",
    "ajustes",
    "documentos",
    "documento_chunks",
    "articulo_chunks",
    "chat_interaccion",
)

# FK simple `portal_id -> portales.id` con nombre explícito (`0006`/`0008`).
# `articulo_relacionados` no tiene FK simple propia (solo las compuestas hacia
# `articulos`, más abajo), así que no aparece aquí.
_FK_PORTAL_NOMBRADA = {
    "categorias": "fk_categorias_portal",
    "categoria_traducciones": "fk_categoria_traducciones_portal",
    "articulos": "fk_articulos_portal",
    "articulo_traducciones": "fk_articulo_traducciones_portal",
    "preguntas_sin_resolver": "fk_preguntas_sin_resolver_portal",
    "conversaciones": "fk_conversaciones_portal",
    "metricas": "fk_metricas_portal",
    "admin_users": "fk_admin_users_portal",
    "ajustes": "fk_ajustes_portal",
    "documentos": "fk_documentos_portal",
    "documento_chunks": "fk_documento_chunks_portal",
    "articulo_chunks": "fk_articulo_chunks_portal",
}

# `dominios` y `chat_interaccion` declararon su FK simple inline (sin `name=`
# ni `op.create_foreign_key`), así que Postgres las auto-nombró
# `{tabla}_portal_id_fkey` (`0006`/`0011`). Ambas llevan CASCADE. Se
# recrean con nombre explícito (mejora sobre el auto-nombre original).
_FK_PORTAL_AUTO = {
    "dominios": "dominios_portal_id_fkey",
    "chat_interaccion": "chat_interaccion_portal_id_fkey",
}
_FK_PORTAL_AUTO_NUEVO_NOMBRE = {
    "dominios": "fk_dominios_portal",
    "chat_interaccion": "fk_chat_interaccion_portal",
}

# FKs compuestas `(portal_id, x_id) -> articulos/categorias(portal_id, id)`.
# `(tabla, nombre, columna_local, tabla_padre, ondelete, deferrable)`.
_FK_COMPUESTAS = (
    ("categoria_traducciones", "fk_categoria_trad_categoria", "categoria_id", "categorias", "CASCADE", False),
    ("articulos", "fk_articulos_categoria", "categoria_id", "categorias", None, False),
    ("articulo_traducciones", "fk_articulo_trad_articulo", "articulo_id", "articulos", "CASCADE", False),
    ("articulo_relacionados", "fk_articulo_relacionados_articulo", "articulo_id", "articulos", "CASCADE", False),
    ("articulo_relacionados", "fk_articulo_relacionados_relacionado", "relacionado_id", "articulos", "CASCADE", True),
    ("articulo_chunks", "fk_articulo_chunks_articulo", "articulo_id", "articulos", "CASCADE", False),
)

# PKs compuestas que llevan `portal_id` de primera columna.
_PKS_COMPUESTAS = {
    "categorias": ["portal_id", "id"],
    "articulos": ["portal_id", "id"],
    "categoria_traducciones": ["portal_id", "categoria_id", "idioma"],
    "articulo_traducciones": ["portal_id", "articulo_id", "idioma"],
    "articulo_relacionados": ["portal_id", "articulo_id", "relacionado_id"],
    "conversaciones": ["portal_id", "idioma"],
    "metricas": ["portal_id", "idioma", "clave"],
}

# Uniques que llevan `portal_id`.
_UNIQUES = {
    "categoria_traducciones": ("uq_categoria_trad_portal_slug", ["portal_id", "idioma", "slug"]),
    "articulo_traducciones": ("uq_articulo_trad_portal_slug", ["portal_id", "idioma", "slug"]),
    "admin_users": ("uq_admin_users_portal_email", ["portal_id", "email"]),
    "ajustes": ("uq_ajustes_portal", ["portal_id"]),
}

# Índices simples `ix_{tabla}_portal_id` (todas menos `articulo_relacionados`,
# que no tiene índice propio de portal: su PK ya lo cubre).
_INDICES_SIMPLES = (
    "dominios", "categorias", "categoria_traducciones", "articulos",
    "articulo_traducciones", "preguntas_sin_resolver", "admin_users",
    "documentos", "documento_chunks", "articulo_chunks",
)


def _backfill_portal_id(tabla: str, columna_portales: str) -> None:
    op.add_column(tabla, sa.Column("portal_id_nuevo", PG_UUID(as_uuid=True), nullable=True))
    op.execute(
        f"UPDATE {tabla} AS t SET portal_id_nuevo = p.{columna_portales} "
        f"FROM portales AS p WHERE p.id = t.portal_id"
    )
    op.alter_column(tabla, "portal_id_nuevo", nullable=False)


def upgrade() -> None:
    # 1. `portales.id_nuevo`: UUID fijo para `default`/`platform`, aleatorio
    #    para el resto. Nullable hasta el backfill para no romper filas
    #    existentes; `NOT NULL` al final de este paso.
    op.add_column("portales", sa.Column("id_nuevo", PG_UUID(as_uuid=True), nullable=True))
    op.execute(
        sa.text(
            "UPDATE portales SET id_nuevo = CASE "
            "WHEN slug = :slug_default THEN CAST(:uuid_default AS uuid) "
            "WHEN slug = :slug_plataforma THEN CAST(:uuid_plataforma AS uuid) "
            "ELSE gen_random_uuid() END"
        ).bindparams(
            slug_default=PORTAL_DEFECTO_SLUG,
            uuid_default=PORTAL_DEFECTO_UUID,
            slug_plataforma=PORTAL_PLATAFORMA_SLUG,
            uuid_plataforma=PORTAL_PLATAFORMA_UUID,
        )
    )
    op.alter_column("portales", "id_nuevo", nullable=False)

    # 2. `portal_id_nuevo` en las 15 tablas hijas, backfilleado por join contra
    #    `portales` (todavía con el `id` viejo): DEBE ir antes de tocar
    #    `portales.id`, porque el join usa `p.id = t.portal_id`.
    for tabla in _TABLAS_PORTAL_ID:
        _backfill_portal_id(tabla, "id_nuevo")

    # 3. Soltar lo que depende del tipo `String`, de hijos a padres: primero las
    #    FKs compuestas hacia `articulos`/`categorias` (su `portal_id` cambia en
    #    ambos extremos), luego las FKs simples hacia `portales.id`, luego las
    #    PKs/uniques compuestas y por último la PK de `portales`.
    for tabla, nombre, _col, _padre, _ondelete, _deferrable in _FK_COMPUESTAS:
        op.drop_constraint(nombre, tabla, type_="foreignkey")

    for tabla, nombre in _FK_PORTAL_NOMBRADA.items():
        op.drop_constraint(nombre, tabla, type_="foreignkey")
    for tabla, nombre in _FK_PORTAL_AUTO.items():
        op.drop_constraint(nombre, tabla, type_="foreignkey")

    for tabla, _cols in _PKS_COMPUESTAS.items():
        op.drop_constraint(f"{tabla}_pkey", tabla, type_="primary")
    for tabla, (nombre, _cols) in _UNIQUES.items():
        op.drop_constraint(nombre, tabla, type_="unique")
    for tabla in _INDICES_SIMPLES:
        op.drop_index(f"ix_{tabla}_portal_id", table_name=tabla)
    op.drop_index("ix_articulo_chunks_articulo", table_name="articulo_chunks")
    op.drop_index("ix_chat_interaccion_portal_creado", table_name="chat_interaccion")

    op.drop_constraint("portales_pkey", "portales", type_="primary")

    # 4. Soltar las columnas viejas (`String`) y renombrar las nuevas (`UUID`).
    for tabla in _TABLAS_PORTAL_ID:
        op.drop_column(tabla, "portal_id")
        op.alter_column(tabla, "portal_id_nuevo", new_column_name="portal_id")
    op.drop_column("portales", "id")
    op.alter_column("portales", "id_nuevo", new_column_name="id")

    # 5. Reconstruir todo con el tipo `UUID`. Las PKs compuestas van ANTES que las
    #    FKs compuestas: `fk_categoria_trad_categoria`/`fk_articulos_categoria`
    #    apuntan a `categorias(portal_id, id)` y `fk_articulo_trad_articulo`/
    #    `fk_articulo_relacionados_*`/`fk_articulo_chunks_articulo` a
    #    `articulos(portal_id, id)`; Postgres exige que exista una restricción
    #    única sobre esas columnas en la tabla referenciada antes de aceptar la FK.
    op.create_primary_key("portales_pkey", "portales", ["id"])

    for tabla, nombre in _FK_PORTAL_NOMBRADA.items():
        op.create_foreign_key(nombre, tabla, "portales", ["portal_id"], ["id"])
    for tabla, nombre_auto in _FK_PORTAL_AUTO.items():
        op.create_foreign_key(
            _FK_PORTAL_AUTO_NUEVO_NOMBRE[tabla], tabla, "portales", ["portal_id"], ["id"],
            ondelete="CASCADE",
        )

    for tabla, cols in _PKS_COMPUESTAS.items():
        op.create_primary_key(f"{tabla}_pkey", tabla, cols)

    for tabla, nombre, columna, padre, ondelete, deferrable in _FK_COMPUESTAS:
        kwargs = {"ondelete": ondelete} if ondelete else {}
        if deferrable:
            kwargs.update(deferrable=True, initially="DEFERRED")
        op.create_foreign_key(
            nombre, tabla, padre, ["portal_id", columna], ["portal_id", "id"], **kwargs
        )

    for tabla, (nombre, cols) in _UNIQUES.items():
        op.create_unique_constraint(nombre, tabla, cols)
    for tabla in _INDICES_SIMPLES:
        op.create_index(f"ix_{tabla}_portal_id", tabla, ["portal_id"])
    op.create_index(
        "ix_articulo_chunks_articulo", "articulo_chunks", ["portal_id", "articulo_id"]
    )
    op.create_index(
        "ix_chat_interaccion_portal_creado",
        "chat_interaccion",
        ["portal_id", sa.text("creado_en DESC")],
    )


def downgrade() -> None:
    # Inverso exacto: vuelve a `String`, con `portales.id` backfilleado a su
    # propio `slug` (el invariante `id == slug` de antes de esta migración) y
    # el `portal_id` de cada tabla hija al `slug` de su portal.

    # 1. `portales.id_viejo`: el slug de cada fila.
    op.add_column("portales", sa.Column("id_viejo", sa.String(), nullable=True))
    op.execute("UPDATE portales SET id_viejo = slug")
    op.alter_column("portales", "id_viejo", nullable=False)

    # 2. `portal_id_viejo` en las 15 tablas hijas, backfilleado por join contra
    #    `portales` (todavía con el `id` UUID actual).
    for tabla in _TABLAS_PORTAL_ID:
        op.add_column(tabla, sa.Column("portal_id_viejo", sa.String(), nullable=True))
        op.execute(
            f"UPDATE {tabla} AS t SET portal_id_viejo = p.id_viejo "
            f"FROM portales AS p WHERE p.id = t.portal_id"
        )
        op.alter_column(tabla, "portal_id_viejo", nullable=False)

    # 3. Soltar lo que depende del tipo `UUID`, de hijos a padres (mismo orden
    #    que en `upgrade`).
    for tabla, nombre, _col, _padre, _ondelete, _deferrable in _FK_COMPUESTAS:
        op.drop_constraint(nombre, tabla, type_="foreignkey")

    for tabla, nombre in _FK_PORTAL_NOMBRADA.items():
        op.drop_constraint(nombre, tabla, type_="foreignkey")
    for tabla, nombre_nuevo in _FK_PORTAL_AUTO_NUEVO_NOMBRE.items():
        op.drop_constraint(nombre_nuevo, tabla, type_="foreignkey")

    for tabla, _cols in _PKS_COMPUESTAS.items():
        op.drop_constraint(f"{tabla}_pkey", tabla, type_="primary")
    for tabla, (nombre, _cols) in _UNIQUES.items():
        op.drop_constraint(nombre, tabla, type_="unique")
    for tabla in _INDICES_SIMPLES:
        op.drop_index(f"ix_{tabla}_portal_id", table_name=tabla)
    op.drop_index("ix_articulo_chunks_articulo", table_name="articulo_chunks")
    op.drop_index("ix_chat_interaccion_portal_creado", table_name="chat_interaccion")

    op.drop_constraint("portales_pkey", "portales", type_="primary")

    # 4. Soltar las columnas UUID y renombrar las `String` de vuelta a su nombre.
    for tabla in _TABLAS_PORTAL_ID:
        op.drop_column(tabla, "portal_id")
        op.alter_column(tabla, "portal_id_viejo", new_column_name="portal_id")
    op.drop_column("portales", "id")
    op.alter_column("portales", "id_viejo", new_column_name="id")

    # 5. Reconstruir todo con el tipo `String`, exactamente como antes de `0012`.
    #    Mismo orden que en `upgrade`: las PKs compuestas antes que las FKs
    #    compuestas que las referencian (ver el comentario allí).
    op.create_primary_key("portales_pkey", "portales", ["id"])

    for tabla, nombre in _FK_PORTAL_NOMBRADA.items():
        op.create_foreign_key(nombre, tabla, "portales", ["portal_id"], ["id"])
    for tabla, nombre_auto in _FK_PORTAL_AUTO.items():
        op.create_foreign_key(
            nombre_auto, tabla, "portales", ["portal_id"], ["id"], ondelete="CASCADE"
        )

    for tabla, cols in _PKS_COMPUESTAS.items():
        op.create_primary_key(f"{tabla}_pkey", tabla, cols)

    for tabla, nombre, columna, padre, ondelete, deferrable in _FK_COMPUESTAS:
        kwargs = {"ondelete": ondelete} if ondelete else {}
        if deferrable:
            kwargs.update(deferrable=True, initially="DEFERRED")
        op.create_foreign_key(
            nombre, tabla, padre, ["portal_id", columna], ["portal_id", "id"], **kwargs
        )

    for tabla, (nombre, cols) in _UNIQUES.items():
        op.create_unique_constraint(nombre, tabla, cols)
    for tabla in _INDICES_SIMPLES:
        op.create_index(f"ix_{tabla}_portal_id", tabla, ["portal_id"])
    op.create_index(
        "ix_articulo_chunks_articulo", "articulo_chunks", ["portal_id", "articulo_id"]
    )
    op.create_index(
        "ix_chat_interaccion_portal_creado",
        "chat_interaccion",
        ["portal_id", sa.text("creado_en DESC")],
    )
