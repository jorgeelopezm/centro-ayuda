"""Resolución del portal (tenant) a partir del host de la petición.

El portal se decide SIEMPRE en el servidor a partir del host, nunca de un parámetro,
cabecera de aplicación o cuerpo del cliente (ver spec `resolucion-portal-por-dominio`).
El orden es: (1) coincidencia exacta en la tabla `dominios` —el subdominio del portal
y los dominios propios mapeados—, y si no la hay, (2) el slug del subdominio bajo el
dominio base. Nunca se cae a un portal por defecto arbitrario: un host desconocido
resuelve a `None` y el llamador responde de forma segura (404 «portal no encontrado»).

Las dos funciones de troceo de host (`normalizar_host`, `extraer_subdominio`) son puras
—sin base de datos— para poder fijarlas con tests de lógica pura.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Dominio, Portal
from app.servicios import PORTAL_PLATAFORMA_SLUG

# Slugs/hosts reservados: nombres de infraestructura que un subdominio de cliente
# nunca puede reclamar. Un subdominio que coincida con uno de estos NO resuelve a
# ningún portal (evita que `www.tuapp.com` o `api.tuapp.com` se confundan con un
# portal). Incluye el slug del portal de plataforma (hogar del SuperAdmin), que
# tampoco es un portal de contenido servible por host.
SLUGS_RESERVADOS: frozenset[str] = frozenset(
    {"www", "api", "admin", "app", "static", "assets", "cdn", "mail", "ftp", PORTAL_PLATAFORMA_SLUG}
)


def normalizar_host(host: str | None) -> str:
    """Host en minúsculas y sin puerto. `None`/vacío → cadena vacía.

    `Ejemplo.com:8000` → `ejemplo.com`. Los portales se sirven por nombre de host, no
    por IP literal, así que no se contempla el caso IPv6 entre corchetes.
    """
    if not host:
        return ""
    return host.strip().lower().split(":", 1)[0]


def extraer_subdominio(host: str | None, base_domain: str) -> str | None:
    """Slug del subdominio de `host` bajo `base_domain`, o `None` si no aplica.

    `cliente1.tuapp.com` bajo `tuapp.com` → `cliente1`. El propio dominio base, un host
    ajeno o un subdominio de varios niveles (`a.b.tuapp.com`) devuelven `None`: solo se
    admite un nivel de subdominio como slug de portal.
    """
    host = normalizar_host(host)
    sufijo = "." + base_domain.strip().lower()
    if not host.endswith(sufijo):
        return None
    etiqueta = host[: -len(sufijo)]
    if not etiqueta or "." in etiqueta:
        return None
    return etiqueta


def resolver_portal(db: Session, host: str | None, *, base_domain: str) -> Portal | None:
    """Portal para `host`, o `None` si ninguno corresponde.

    Primero la coincidencia exacta en `dominios` (subdominio del portal y dominios
    propios), luego el slug del subdominio bajo `base_domain`. Los slugs reservados no
    resuelven. Nunca devuelve un portal por defecto para un host desconocido.
    """
    host = normalizar_host(host)
    if not host:
        return None

    dominio = db.query(Dominio).filter(Dominio.host == host).first()
    if dominio is not None:
        return db.get(Portal, dominio.portal_id)

    slug = extraer_subdominio(host, base_domain)
    if slug is None or slug in SLUGS_RESERVADOS:
        return None
    return db.query(Portal).filter(Portal.slug == slug).first()
