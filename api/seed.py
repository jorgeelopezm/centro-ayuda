"""Carga el contenido exportado (`api/seed_data/{es,pt}.json`) en la base de datos
y siembra el administrador inicial.

Requiere el esquema ya migrado (`alembic upgrade head`) y el JSON ya exportado
(`node app/scripts/exportar-datos.mjs`). Es idempotente: vacía las tablas de
contenido y las vuelve a poblar; el administrador se crea solo si no existe.

Uso desde `api/`:  python seed.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    AdminUser,
    Ajustes,
    Articulo,
    ArticuloRelacionado,
    ArticuloTraduccion,
    Categoria,
    CategoriaTraduccion,
    Conversacion,
    Dominio,
    Metrica,
    NivelAcceso,
    Portal,
    PreguntaSinResolver,
)
from app.security import hash_password
from app.servicios import (
    AJUSTES_ID,
    IDIOMAS,
    PORTAL_DEFECTO_HOST,
    PORTAL_DEFECTO_SLUG,
    PORTAL_DEFECTO_UUID,
    PORTAL_PLATAFORMA_EMPRESA,
    PORTAL_PLATAFORMA_HOST_DEV,
    PORTAL_PLATAFORMA_SLUG,
    PORTAL_PLATAFORMA_UUID,
    host_plataforma,
)

SEED_DIR = Path(__file__).parent / "seed_data"


def _cargar_idiomas() -> dict[str, dict]:
    datos = {}
    for idioma in IDIOMAS:
        ruta = SEED_DIR / f"{idioma}.json"
        if not ruta.exists():
            raise SystemExit(
                f"Falta {ruta}. Ejecuta primero: node app/scripts/exportar-datos.mjs"
            )
        datos[idioma] = json.loads(ruta.read_text(encoding="utf-8"))
    return datos


def _por_id(datos: dict[str, dict], clave: str) -> dict[str, dict]:
    """Indexa por id la lista `clave` de cada idioma: `{idioma: {id: item}}`.

    El JSON llega como listas paralelas por idioma. El español marca el orden y
    el conjunto de ids; el resto se busca por id, que es lo único estable entre
    idiomas (slug, título y textos cambian).
    """
    return {idioma: {item["id"]: item for item in datos[idioma][clave]} for idioma in IDIOMAS}


def _vaciar(db) -> None:
    for modelo in (
        ArticuloRelacionado,
        ArticuloTraduccion,
        Articulo,
        CategoriaTraduccion,
        Categoria,
        PreguntaSinResolver,
        Conversacion,
        Metrica,
    ):
        db.query(modelo).delete()


def _sembrar_categorias(db, datos: dict[str, dict]) -> None:
    base = datos["es"]["categorias"]
    por_id = _por_id(datos, "categorias")
    for orden, cat in enumerate(base):
        db.add(
            Categoria(
                id=cat["id"],
                portal_id=PORTAL_DEFECTO_UUID,
                icono=cat["icono"],
                orden=orden,
            )
        )
        for idioma in IDIOMAS:
            t = por_id[idioma][cat["id"]]
            db.add(
                CategoriaTraduccion(
                    categoria_id=cat["id"],
                    portal_id=PORTAL_DEFECTO_UUID,
                    idioma=idioma,
                    slug=t["slug"],
                    nombre=t["nombre"],
                )
            )


def _sembrar_articulos(db, datos: dict[str, dict]) -> None:
    base = datos["es"]["articulos"]
    por_id = _por_id(datos, "articulos")
    for orden, art in enumerate(base):
        db.add(
            Articulo(
                id=art["id"],
                portal_id=PORTAL_DEFECTO_UUID,
                categoria_id=art["categoria"],
                actualizado=date.fromisoformat(art["actualizado"]),
                minutos_lectura=art["minutosLectura"],
                destacado=art["destacado"],
                orden=orden,
            )
        )
        for i, rid in enumerate(art.get("relacionados", [])):
            db.add(
                ArticuloRelacionado(
                    portal_id=PORTAL_DEFECTO_UUID,
                    articulo_id=art["id"],
                    relacionado_id=rid,
                    orden=i,
                )
            )
        for idioma in IDIOMAS:
            t = por_id[idioma][art["id"]]
            db.add(
                ArticuloTraduccion(
                    articulo_id=art["id"],
                    portal_id=PORTAL_DEFECTO_UUID,
                    idioma=idioma,
                    slug=t["slug"],
                    titulo=t["titulo"],
                    parrafos=t["parrafos"],
                    how_to=t["howTo"],
                    nota=t.get("nota"),
                    faq=t["faq"],
                )
            )


def _sembrar_panel(db, datos: dict[str, dict]) -> None:
    for idioma in IDIOMAS:
        contenido = datos[idioma]
        for orden, p in enumerate(contenido["preguntasSinResolver"]):
            db.add(
                PreguntaSinResolver(
                    portal_id=PORTAL_DEFECTO_UUID,
                    idioma=idioma,
                    pregunta=p["pregunta"],
                    veces=p["veces"],
                    similitud=p["similitud"],
                    fecha=date.fromisoformat(p["fecha"]),
                    estado=p["estado"],
                    orden=orden,
                )
            )
        db.add(Conversacion(portal_id=PORTAL_DEFECTO_UUID, idioma=idioma, mensajes=contenido["conversacion"]))
        for orden, m in enumerate(contenido["metricas"]):
            db.add(
                Metrica(
                    portal_id=PORTAL_DEFECTO_UUID,
                    idioma=idioma,
                    clave=m["clave"],
                    valor=m["valor"],
                    orden=orden,
                )
            )


LONGITUD_MINIMA_CONTRASENA = 12
CONTRASENAS_PROHIBIDAS = {"admin", "password", "cambia-esta-contrasena", "contrasena"}


def _exigir_contrasena_fuerte(variable: str, contrasena: str) -> None:
    """El seed es la única vía por la que entra una contraseña de administrador: si
    aquí pasa una trivial, queda para siempre en la base. Falla con un mensaje claro
    que nombra la variable de entorno responsable."""
    if contrasena.lower() in CONTRASENAS_PROHIBIDAS or len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        raise SystemExit(
            f"{variable} es demasiado débil (mínimo {LONGITUD_MINIMA_CONTRASENA} caracteres, "
            'sin valores obvios). Generar una:  python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


def _sembrar_admin(db) -> None:
    s = get_settings()

    _exigir_contrasena_fuerte("ADMIN_PASSWORD", s.admin_password)

    if (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == PORTAL_DEFECTO_UUID, AdminUser.email == s.admin_email)
        .first()
        is not None
    ):
        # Ojo: no se recrea. Para rotar la contraseña hay que borrar la fila antes.
        print(f"Administrador {s.admin_email} ya existe; no se recrea.")
        return
    # El administrador inicial es Administrador: es el primer usuario y quien gestiona a los demás.
    db.add(
        AdminUser(
            portal_id=PORTAL_DEFECTO_UUID,
            email=s.admin_email,
            password_hash=hash_password(s.admin_password),
            nivel=NivelAcceso.ADMINISTRADOR.value,
            activo=True,
        )
    )
    print(f"Administrador {s.admin_email} creado (Administrador).")


def _sembrar_superadmin(db) -> None:
    """Provisiona el portal de plataforma y su SuperAdmin (nivel 4) si hay credenciales.

    Es opcional: sin `SUPERADMIN_PASSWORD` no se crea nada y el entorno single-portal
    funciona igual. El SuperAdmin es transversal (gestiona portales), así que vive en el
    portal de plataforma reservado, no en un portal de contenido. Idempotente."""
    s = get_settings()
    if not s.superadmin_password:
        print("SUPERADMIN_PASSWORD sin definir; no se crea SuperAdmin (opcional).")
        return

    _exigir_contrasena_fuerte("SUPERADMIN_PASSWORD", s.superadmin_password)

    # El portal de plataforma es el hogar del SuperAdmin; se crea junto a él (no sirve
    # contenido ni tiene host). Sin él, la FK `admin_users.portal_id` no resolvería.
    if db.get(Portal, PORTAL_PLATAFORMA_UUID) is None:
        db.add(
            Portal(
                id=PORTAL_PLATAFORMA_UUID,
                slug=PORTAL_PLATAFORMA_SLUG,
                nombre_empresa=PORTAL_PLATAFORMA_EMPRESA,
                estado="activo",
            )
        )
        db.flush()
        print(f"Portal de plataforma {PORTAL_PLATAFORMA_SLUG!r} creado ({PORTAL_PLATAFORMA_UUID}).")

    # Hosts de gestión por los que entra el SuperAdmin: `admin.localhost` (desarrollo) y
    # `admin.<base_domain>` (producción). El slug `platform` está reservado y no resuelve
    # por subdominio, así que estas filas exactas en `dominios` son su única puerta. Se
    # añaden aunque el portal ya existiera (re-seed que rellena hosts que faltasen).
    #
    # En desarrollo (`BASE_DOMAIN=localhost`) los dos hosts son el MISMO `admin.localhost`,
    # así que hay que descartar el repetido: `autoflush=False` hace que la consulta de
    # existencia no vea el `db.add` pendiente, y el INSERT por lotes chocaría con la PK de
    # `dominios`. Gana el primer par (el principal), que es el host canónico.
    vistos: set[str] = set()
    for host, principal in (
        (host_plataforma(s.base_domain), True),
        (PORTAL_PLATAFORMA_HOST_DEV, False),
    ):
        if host in vistos:
            continue
        vistos.add(host)
        if db.query(Dominio).filter(Dominio.host == host).first() is None:
            db.add(Dominio(host=host, portal_id=PORTAL_PLATAFORMA_UUID, principal=principal))
            print(f"Host de gestión {host!r} → portal de plataforma.")

    if (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == PORTAL_PLATAFORMA_UUID, AdminUser.email == s.superadmin_email)
        .first()
        is not None
    ):
        print(f"SuperAdmin {s.superadmin_email} ya existe; no se recrea.")
        return
    db.add(
        AdminUser(
            portal_id=PORTAL_PLATAFORMA_UUID,
            email=s.superadmin_email,
            password_hash=hash_password(s.superadmin_password),
            nivel=NivelAcceso.SUPERADMIN.value,
            activo=True,
        )
    )
    print(f"SuperAdmin {s.superadmin_email} creado (nivel 4).")


def _sembrar_portal(db) -> None:
    """Crea el portal `default` y su host de desarrollo (`localhost`) si no existen.

    En un despliegue real la migración `0006_portales` ya los crea; el seed los
    asegura para el flujo de desarrollo (base recreada sin ejecutar esa migración) y
    sincroniza el nombre de empresa con el valor de configuración. Idempotente."""
    s = get_settings()
    portal = db.get(Portal, PORTAL_DEFECTO_UUID)
    if portal is None:
        db.add(
            Portal(
                id=PORTAL_DEFECTO_UUID,
                slug=PORTAL_DEFECTO_SLUG,
                nombre_empresa=s.empresa_inicial,
                estado="activo",
            )
        )
        db.add(Dominio(host=PORTAL_DEFECTO_HOST, portal_id=PORTAL_DEFECTO_UUID, principal=True))
        db.flush()
        print(f"Portal {PORTAL_DEFECTO_SLUG!r} creado (host {PORTAL_DEFECTO_HOST}).")
    else:
        print(f"Portal {PORTAL_DEFECTO_SLUG!r} ya existe; no se recrea.")


def _sembrar_ajustes(db) -> None:
    """Crea la fila de marca visual del portal `default` (acento/banner/logo por defecto).

    El nombre de empresa NO va aquí: vive en `Portal.nombre_empresa`, que ya siembra
    `_sembrar_portal_default` con el valor de configuración. Idempotente: si la fila ya
    existe, no la pisa (para no revertir un cambio hecho desde el panel al re-sembrar)."""
    if db.get(Ajustes, AJUSTES_ID) is not None:
        print("Ajustes ya existen; no se recrean.")
        return
    db.add(Ajustes(id=AJUSTES_ID, portal_id=PORTAL_DEFECTO_UUID))
    print("Ajustes de marca visual creados para el portal 'default'.")


def main() -> None:
    datos = _cargar_idiomas()
    db = SessionLocal()
    try:
        _vaciar(db)
        # El portal `default` va primero: las FKs `portal_id` del contenido lo exigen.
        _sembrar_portal(db)
        db.flush()
        _sembrar_categorias(db, datos)
        # Fuerza el INSERT de categorías antes que el de artículos: no hay relación ORM
        # entre `Articulo` y `Categoria`, así que sin este flush el orden de volcado no
        # está garantizado y PostgreSQL rechaza la FK `articulos.categoria_id`.
        db.flush()
        _sembrar_articulos(db, datos)
        _sembrar_panel(db, datos)
        _sembrar_admin(db)
        _sembrar_superadmin(db)
        _sembrar_ajustes(db)
        db.commit()
        n = len(datos["es"]["articulos"])
        print(f"Seed completado: {n} artículos en {', '.join(IDIOMAS)}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
