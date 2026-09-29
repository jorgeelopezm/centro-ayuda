"""Multi-tenant: tabla `portales`/`dominios` y `portal_id` en el contenido y usuarios.

Introduce el aislamiento por portal (tenant). Crea las tablas `portales` y `dominios`,
siembra un portal **`default`** (con su host de desarrollo `localhost` y el nombre de
empresa tomado de los ajustes existentes), y añade `portal_id` a las tablas de
contenido y de usuarios. El patrón es el seguro para columnas obligatorias nuevas con
datos existentes: **añadir nullable → *backfill* a `default` → imponer NOT NULL + FK**,
por lo que no se pierde ningún dato y el contenido single-tenant actual queda bajo el
portal `default`.

También:
- Hace **compuestas por portal** las unicidades antes globales: `(portal_id, email)` en
  `admin_users` (sustituye a la unicidad global de `email`) y `(portal_id, idioma, slug)`
  en las traducciones de artículos y categorías.
- Amplía la clave primaria de `conversaciones` y `metricas` para incluir `portal_id`.
- Deja `ajustes` con una fila de marca por portal (`portal_id` único).

Es reversible (`downgrade` devuelve el modelo single-tenant con los datos del portal
`default`).

Revision ID: 0006_portales
Revises: 0005, 0005_marca
Create Date: 2026-08-16

Nota: `down_revision` es una tupla porque esta migración **fusiona las dos cabezas**
que colgaban de `0004` (`0005` de la rama de FK de relacionados y `0005_marca` de la
marca visual), como anticipaba la nota de `0005_marca`. Sustituye a un `alembic merge
heads` vacío: además de fusionar, aplica el cambio multi-tenant.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_portales"
down_revision: Union[str, Sequence[str], None] = ("0005", "0005_marca")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Identidad del portal por defecto (espejo de app.servicios.PORTAL_DEFECTO_*).
PORTAL_DEFECTO_ID = "default"
PORTAL_DEFECTO_SLUG = "default"
PORTAL_DEFECTO_HOST = "localhost"
EMPRESA_POR_DEFECTO = "[Empresa]"

# Tablas de contenido/usuarios que solo necesitan `portal_id` + índice + FK.
_TABLAS_SIMPLES = ("categorias", "articulos", "preguntas_sin_resolver")


def _add_portal_id(tabla: str) -> None:
    """Añade `portal_id` a una tabla existente sin perder datos: nullable → backfill
    a `default` → NOT NULL, con su índice y su FK a `portales`."""
    op.add_column(tabla, sa.Column("portal_id", sa.String(), nullable=True))
    op.execute(sa.text(f"UPDATE {tabla} SET portal_id = :pid").bindparams(pid=PORTAL_DEFECTO_ID))
    op.alter_column(tabla, "portal_id", nullable=False)
    op.create_index(f"ix_{tabla}_portal_id", tabla, ["portal_id"])
    op.create_foreign_key(f"fk_{tabla}_portal", tabla, "portales", ["portal_id"], ["id"])


def _drop_portal_id(tabla: str) -> None:
    op.drop_constraint(f"fk_{tabla}_portal", tabla, type_="foreignkey")
    op.drop_index(f"ix_{tabla}_portal_id", table_name=tabla)
    op.drop_column(tabla, "portal_id")


def upgrade() -> None:
    # 1. Tablas de portal y su portal `default` (los backfills posteriores dependen de él).
    op.create_table(
        "portales",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("nombre_empresa", sa.String(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False, server_default="activo"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_portales_slug", "portales", ["slug"], unique=True)

    op.create_table(
        "dominios",
        sa.Column("host", sa.String(), primary_key=True),
        sa.Column("portal_id", sa.String(), sa.ForeignKey("portales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("principal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dominios_portal_id", "dominios", ["portal_id"])

    # El nombre de empresa del portal `default` sale de los ajustes existentes (si la
    # base ya tenía contenido); en una base recién migrada aún no hay ajustes y se usa
    # el valor de reserva, que el seed sobrescribe con el real.
    bind = op.get_bind()
    empresa = bind.execute(sa.text("SELECT empresa FROM ajustes WHERE id = 1")).scalar()
    op.execute(
        sa.text(
            "INSERT INTO portales (id, slug, nombre_empresa, estado) "
            "VALUES (:id, :slug, :empresa, 'activo')"
        ).bindparams(id=PORTAL_DEFECTO_ID, slug=PORTAL_DEFECTO_SLUG, empresa=empresa or EMPRESA_POR_DEFECTO)
    )
    op.execute(
        sa.text(
            "INSERT INTO dominios (host, portal_id, principal) VALUES (:host, :pid, true)"
        ).bindparams(host=PORTAL_DEFECTO_HOST, pid=PORTAL_DEFECTO_ID)
    )

    # 2. `portal_id` en las tablas simples de contenido.
    for tabla in _TABLAS_SIMPLES:
        _add_portal_id(tabla)

    # 3. Traducciones: `portal_id` denormalizado desde el padre + unicidad de slug por
    #    portal e idioma. El backfill toma el portal del artículo/categoría padre.
    for tabla, padre, fk_padre in (
        ("categoria_traducciones", "categorias", "categoria_id"),
        ("articulo_traducciones", "articulos", "articulo_id"),
    ):
        op.add_column(tabla, sa.Column("portal_id", sa.String(), nullable=True))
        op.execute(
            f"UPDATE {tabla} AS t SET portal_id = p.portal_id "
            f"FROM {padre} AS p WHERE p.id = t.{fk_padre}"
        )
        op.alter_column(tabla, "portal_id", nullable=False)
        op.create_index(f"ix_{tabla}_portal_id", tabla, ["portal_id"])
        op.create_foreign_key(f"fk_{tabla}_portal", tabla, "portales", ["portal_id"], ["id"])
        sufijo = "categoria" if tabla == "categoria_traducciones" else "articulo"
        op.create_unique_constraint(
            f"uq_{sufijo}_trad_portal_slug", tabla, ["portal_id", "idioma", "slug"]
        )

    # 3b. PK compuesta `(portal_id, id)` en `categorias` y `articulos`: el id de
    #     contenido pasa a ser único *por portal*, no global. Requiere reescribir como
    #     compuestas las FKs que apuntaban a esas PKs (traducciones, la categoría del
    #     artículo y los relacionados), y dar a `articulo_relacionados` su `portal_id`.
    #
    #     Los enlaces relacionados son intra-portal: `portal_id` sale del artículo origen.
    op.add_column("articulo_relacionados", sa.Column("portal_id", sa.String(), nullable=True))
    op.execute(
        "UPDATE articulo_relacionados AS r SET portal_id = a.portal_id "
        "FROM articulos AS a WHERE a.id = r.articulo_id"
    )
    op.alter_column("articulo_relacionados", "portal_id", nullable=False)

    # Las traducciones también llevan el portal en su PK: su id de padre ya no es único
    # global, así que `(padre_id, idioma)` podía chocar entre portales.
    op.drop_constraint("categoria_traducciones_pkey", "categoria_traducciones", type_="primary")
    op.create_primary_key(
        "categoria_traducciones_pkey", "categoria_traducciones", ["portal_id", "categoria_id", "idioma"]
    )
    op.drop_constraint("articulo_traducciones_pkey", "articulo_traducciones", type_="primary")
    op.create_primary_key(
        "articulo_traducciones_pkey", "articulo_traducciones", ["portal_id", "articulo_id", "idioma"]
    )

    # Soltar primero las FKs hijas (nombres autogenerados por Postgres en `0001`, salvo
    # la de `relacionado_id`, explícita en `0005`) para poder cambiar las PKs padre.
    op.drop_constraint("fk_articulo_relacionados_relacionado_id", "articulo_relacionados", type_="foreignkey")
    op.drop_constraint("articulo_relacionados_articulo_id_fkey", "articulo_relacionados", type_="foreignkey")
    op.drop_constraint("articulo_traducciones_articulo_id_fkey", "articulo_traducciones", type_="foreignkey")
    op.drop_constraint("articulos_categoria_id_fkey", "articulos", type_="foreignkey")
    op.drop_constraint("categoria_traducciones_categoria_id_fkey", "categoria_traducciones", type_="foreignkey")

    # Cambiar las PKs por sus versiones compuestas (portal_id primero).
    op.drop_constraint("articulo_relacionados_pkey", "articulo_relacionados", type_="primary")
    op.drop_constraint("articulos_pkey", "articulos", type_="primary")
    op.drop_constraint("categorias_pkey", "categorias", type_="primary")
    op.create_primary_key("categorias_pkey", "categorias", ["portal_id", "id"])
    op.create_primary_key("articulos_pkey", "articulos", ["portal_id", "id"])
    op.create_primary_key(
        "articulo_relacionados_pkey", "articulo_relacionados", ["portal_id", "articulo_id", "relacionado_id"]
    )

    # Recrear las FKs hijas como compuestas contra las nuevas PKs por portal.
    op.create_foreign_key(
        "fk_categoria_trad_categoria", "categoria_traducciones", "categorias",
        ["portal_id", "categoria_id"], ["portal_id", "id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_articulos_categoria", "articulos", "categorias",
        ["portal_id", "categoria_id"], ["portal_id", "id"],
    )
    op.create_foreign_key(
        "fk_articulo_trad_articulo", "articulo_traducciones", "articulos",
        ["portal_id", "articulo_id"], ["portal_id", "id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_articulo_relacionados_articulo", "articulo_relacionados", "articulos",
        ["portal_id", "articulo_id"], ["portal_id", "id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_articulo_relacionados_relacionado", "articulo_relacionados", "articulos",
        ["portal_id", "relacionado_id"], ["portal_id", "id"], ondelete="CASCADE",
        deferrable=True, initially="DEFERRED",
    )

    # 4. `conversaciones` y `metricas`: `portal_id` entra en la clave primaria.
    for tabla in ("conversaciones", "metricas"):
        op.add_column(tabla, sa.Column("portal_id", sa.String(), nullable=True))
        op.execute(sa.text(f"UPDATE {tabla} SET portal_id = :pid").bindparams(pid=PORTAL_DEFECTO_ID))
        op.alter_column(tabla, "portal_id", nullable=False)
        op.drop_constraint(f"{tabla}_pkey", tabla, type_="primary")
        op.create_foreign_key(f"fk_{tabla}_portal", tabla, "portales", ["portal_id"], ["id"])
    op.create_primary_key("conversaciones_pkey", "conversaciones", ["portal_id", "idioma"])
    op.create_primary_key("metricas_pkey", "metricas", ["portal_id", "idioma", "clave"])

    # 5. `admin_users`: unicidad de email global → compuesta `(portal_id, email)`.
    _add_portal_id("admin_users")
    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.execute("ALTER TABLE admin_users DROP CONSTRAINT IF EXISTS admin_users_email_key")
    op.create_index("ix_admin_users_email", "admin_users", ["email"])
    op.create_unique_constraint("uq_admin_users_portal_email", "admin_users", ["portal_id", "email"])

    # 6. `ajustes`: una fila de marca por portal (`portal_id` único).
    op.add_column("ajustes", sa.Column("portal_id", sa.String(), nullable=True))
    op.execute(sa.text("UPDATE ajustes SET portal_id = :pid").bindparams(pid=PORTAL_DEFECTO_ID))
    op.alter_column("ajustes", "portal_id", nullable=False)
    op.create_unique_constraint("uq_ajustes_portal", "ajustes", ["portal_id"])
    op.create_foreign_key("fk_ajustes_portal", "ajustes", "portales", ["portal_id"], ["id"])


def downgrade() -> None:
    # Inverso exacto de upgrade. Vuelve al modelo single-tenant: los datos del portal
    # `default` quedan como estaban, sin `portal_id`.

    # Reverso de 3b: soltar las FKs compuestas y las PKs por portal, volver a PKs simples
    # globales y a las FKs simples de `0001`/`0005`, y quitar el `portal_id` de
    # `articulo_relacionados`. Debe ir antes de retirar los `portal_id` del resto.
    op.drop_constraint("fk_articulo_relacionados_relacionado", "articulo_relacionados", type_="foreignkey")
    op.drop_constraint("fk_articulo_relacionados_articulo", "articulo_relacionados", type_="foreignkey")
    op.drop_constraint("fk_articulo_trad_articulo", "articulo_traducciones", type_="foreignkey")
    op.drop_constraint("fk_articulos_categoria", "articulos", type_="foreignkey")
    op.drop_constraint("fk_categoria_trad_categoria", "categoria_traducciones", type_="foreignkey")

    op.drop_constraint("articulo_relacionados_pkey", "articulo_relacionados", type_="primary")
    op.drop_constraint("articulos_pkey", "articulos", type_="primary")
    op.drop_constraint("categorias_pkey", "categorias", type_="primary")
    op.create_primary_key("categorias_pkey", "categorias", ["id"])
    op.create_primary_key("articulos_pkey", "articulos", ["id"])
    op.create_primary_key("articulo_relacionados_pkey", "articulo_relacionados", ["articulo_id", "relacionado_id"])

    op.drop_column("articulo_relacionados", "portal_id")

    op.create_foreign_key(
        "categoria_traducciones_categoria_id_fkey", "categoria_traducciones", "categorias",
        ["categoria_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "articulos_categoria_id_fkey", "articulos", "categorias", ["categoria_id"], ["id"],
    )
    op.create_foreign_key(
        "articulo_traducciones_articulo_id_fkey", "articulo_traducciones", "articulos",
        ["articulo_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "articulo_relacionados_articulo_id_fkey", "articulo_relacionados", "articulos",
        ["articulo_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_articulo_relacionados_relacionado_id", "articulo_relacionados", "articulos",
        ["relacionado_id"], ["id"], ondelete="CASCADE", deferrable=True, initially="DEFERRED",
    )

    # Revertir la PK de las traducciones a `(padre_id, idioma)` (sin portal). Debe ir
    # antes de que `_drop_portal_id` retire su columna `portal_id` más abajo.
    op.drop_constraint("articulo_traducciones_pkey", "articulo_traducciones", type_="primary")
    op.create_primary_key("articulo_traducciones_pkey", "articulo_traducciones", ["articulo_id", "idioma"])
    op.drop_constraint("categoria_traducciones_pkey", "categoria_traducciones", type_="primary")
    op.create_primary_key("categoria_traducciones_pkey", "categoria_traducciones", ["categoria_id", "idioma"])

    op.drop_constraint("fk_ajustes_portal", "ajustes", type_="foreignkey")
    op.drop_constraint("uq_ajustes_portal", "ajustes", type_="unique")
    op.drop_column("ajustes", "portal_id")

    op.drop_constraint("uq_admin_users_portal_email", "admin_users", type_="unique")
    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)
    _drop_portal_id("admin_users")

    op.drop_constraint("metricas_pkey", "metricas", type_="primary")
    op.drop_constraint("conversaciones_pkey", "conversaciones", type_="primary")
    for tabla in ("conversaciones", "metricas"):
        op.drop_constraint(f"fk_{tabla}_portal", tabla, type_="foreignkey")
        op.drop_column(tabla, "portal_id")
    op.create_primary_key("conversaciones_pkey", "conversaciones", ["idioma"])
    op.create_primary_key("metricas_pkey", "metricas", ["idioma", "clave"])

    for tabla, sufijo in (
        ("categoria_traducciones", "categoria"),
        ("articulo_traducciones", "articulo"),
    ):
        op.drop_constraint(f"uq_{sufijo}_trad_portal_slug", tabla, type_="unique")
        _drop_portal_id(tabla)

    for tabla in reversed(_TABLAS_SIMPLES):
        _drop_portal_id(tabla)

    op.drop_index("ix_dominios_portal_id", table_name="dominios")
    op.drop_table("dominios")
    op.drop_index("ix_portales_slug", table_name="portales")
    op.drop_table("portales")
