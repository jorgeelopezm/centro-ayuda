"""Lógica de ensamblado del contenido y escritura de artículos, compartida por los routers."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models import (
    AdminUser,
    Ajustes,
    Articulo,
    ArticuloRelacionado,
    ArticuloTraduccion,
    Categoria,
    CategoriaTraduccion,
    Conversacion,
    Documento,
    Metrica,
    Portal,
    PreguntaSinResolver,
)
from app.texto import normalizar_slug

IDIOMAS = ("es", "pt")

# Portal por defecto: alberga el contenido histórico single-tenant tras la migración
# a multi-tenant. La migración `0006_portales` lo crea y hace *backfill* de todo a él;
# el seed lo siembra. Su slug y host de desarrollo son estables; su `id` (UUID desde la
# migración `0012_portal_uuid`) es una constante fija para que tests y fixtures sean
# deterministas y para que el backfill de esa migración reutilice el mismo valor que ya
# tuviera sembrado en la base del usuario.
PORTAL_DEFECTO_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PORTAL_DEFECTO_SLUG = "default"
PORTAL_DEFECTO_HOST = "localhost"

# Portal de plataforma: hogar reservado del/los SuperAdmin (nivel 4), transversales a
# los portales de contenido. No sirve contenido, pero SÍ tiene un host de gestión propio
# (ver `host_plataforma`): el SuperAdmin entra por él para iniciar sesión y gestionar
# portales. Existe también para que `admin_users.portal_id` (NOT NULL) tenga un valor
# válido para el SuperAdmin y para que `(portal_id, email)` siga siendo único entre
# SuperAdmins. Su slug queda reservado (nunca puede pedirlo un portal de cliente). Lo
# siembra `seed.py` junto al SuperAdmin. Su `id` es una constante fija por el mismo
# motivo que `PORTAL_DEFECTO_UUID`.
PORTAL_PLATAFORMA_UUID = uuid.UUID("00000000-0000-0000-0000-000000000002")
PORTAL_PLATAFORMA_SLUG = "platform"
PORTAL_PLATAFORMA_EMPRESA = "Plataforma"

# Host de gestión del portal de plataforma. "admin" es un slug reservado, así que
# `admin.<base_domain>` NO resuelve por la vía de subdominio (la de slug): necesita una
# fila explícita en `dominios`, que `resolver_portal` casa por coincidencia exacta antes
# de mirar el slug. Esa es justamente la puerta del SuperAdmin. En desarrollo se usa
# `admin.localhost` (Chrome/Firefox resuelven `*.localhost` a 127.0.0.1 sin configurar
# nada); en producción, `admin.<base_domain>`. El seed crea ambas filas.
PORTAL_PLATAFORMA_HOST_DEV = "admin.localhost"


def host_plataforma(base_domain: str) -> str:
    """Host canónico de gestión del portal de plataforma en producción: `admin.<base_domain>`."""
    return f"admin.{base_domain}"

# Fila de ajustes del portal `default` y valor de reserva del campo [Empresa] si aún
# no se sembró.
AJUSTES_ID = 1
EMPRESA_POR_DEFECTO = "[Empresa]"

# Valores de reserva de la marca visual, iguales a los `server_default` de la
# migración `0005_marca` y al aspecto índigo actual de `src/index.css`. Se usan si la
# fila de ajustes todavía no existe (antes del seed) o si una columna llega vacía.
ACENTO_POR_DEFECTO = "#4338ca"
BANNER_DESDE_POR_DEFECTO = "#3730a3"
BANNER_MEDIO_POR_DEFECTO = "#4338ca"
BANNER_HASTA_POR_DEFECTO = "#4f46e5"

# Plantillas del centro de ayuda admitidas. Fuente única: la consumen el esquema de
# entrada del endpoint de escritura (`PlantillaIn`, para rechazar con 422 cualquier
# otro valor) y el normalizador de lectura de `obtener_marca` (tolerancia a un valor
# almacenado desconocido). Añadir una plantilla nueva es añadir un valor aquí y su
# rama de presentación en el frontend; la columna es texto, así que no hay migración.
PLANTILLAS_ADMITIDAS = ("default", "documentacion")
PLANTILLA_POR_DEFECTO = "default"


def normalizar_plantilla(valor: str | None) -> str:
    """Plantilla guardada, o `default` si falta o no es una de las admitidas.

    Espeja el patrón defensivo de `obtener_marca` (`ajuste.acento or ACENTO_POR_DEFECTO`):
    un valor desconocido (dato manipulado, columna de una versión futura) nunca deja al
    portal sin plantilla que renderizar; cae a la predeterminada.
    """
    return valor if valor in PLANTILLAS_ADMITIDAS else PLANTILLA_POR_DEFECTO



def _traduccion(entidad, idioma: str):
    return next((t for t in entidad.traducciones if t.idioma == idioma), None)


def fila_ajustes(db: Session, portal_id: str) -> Ajustes | None:
    """Fila de marca del portal, o `None` si aún no existe (p. ej. antes del seed).

    La marca es **por portal**: se busca por `portal_id` (único), no por el id fijo
    histórico. Cada portal tiene a lo sumo una fila de ajustes.
    """
    return db.query(Ajustes).filter(Ajustes.portal_id == portal_id).first()


def obtener_empresa(db: Session, portal_id: str) -> str:
    """Nombre de empresa (valor de [Empresa]) del portal: su fuente única.

    Vive en `Portal.nombre_empresa`, no en los ajustes de marca (spec `gestion-portales`):
    cada portal muestra su propia identidad. Reserva un valor por defecto solo si el portal
    no existiera (situación que `portal_actual` ya descarta con 404 antes de llegar aquí)."""
    portal = db.get(Portal, portal_id)
    return portal.nombre_empresa if portal is not None else EMPRESA_POR_DEFECTO


def obtener_marca(db: Session, portal_id: str) -> dict:
    """Marca visual del portal (acento + tres paradas del banner) para el contenido público.

    Reserva los valores por defecto si la fila de ajustes del portal aún no existe. El
    logo NO viaja aquí (es binario): se sirve por `GET /api/marca/logo`.

    Incluye también la **plantilla** activa del portal: es otra decisión de presentación
    del mismo portal y de la misma fila de ajustes, y viajar en el contenido público es lo
    que permite servir el HTML inicial ya con el armazón correcto. Se normaliza al leer
    (`normalizar_plantilla`): un valor desconocido publicado como `default`.

    `logoVersion` es un hash corto de los bytes del logotipo (o `None` sin logo). El
    frontend lo usa como cache-buster en la URL de la imagen (`?v={version}`), para
    que al cambiar el logotipo el navegador vuelva a pedirlo en vez de reutilizar la
    copia cacheada de la URL anterior. La ausencia de este parámetro haría que la
    cabecera y el favicon siguieran mostrando el logo viejo tras subir uno nuevo.
    """
    ajuste = fila_ajustes(db, portal_id)
    if ajuste is None:
        return {
            "acento": ACENTO_POR_DEFECTO,
            "bannerDesde": BANNER_DESDE_POR_DEFECTO,
            "bannerMedio": BANNER_MEDIO_POR_DEFECTO,
            "bannerHasta": BANNER_HASTA_POR_DEFECTO,
            "plantilla": PLANTILLA_POR_DEFECTO,
            "githubUrl": None,
            "logo": False,
            "logoVersion": None,
        }
    logo_version = (
        hashlib.sha256(ajuste.logo_bin).hexdigest()[:8]
        if ajuste.logo_bin is not None
        else None
    )
    return {
        "acento": ajuste.acento or ACENTO_POR_DEFECTO,
        "bannerDesde": ajuste.banner_desde or BANNER_DESDE_POR_DEFECTO,
        "bannerMedio": ajuste.banner_medio or BANNER_MEDIO_POR_DEFECTO,
        "bannerHasta": ajuste.banner_hasta or BANNER_HASTA_POR_DEFECTO,
        "plantilla": normalizar_plantilla(ajuste.plantilla),
        # Enlace opcional del icono de GitHub (plantilla de documentación).
        "githubUrl": ajuste.github_url,
        # Solo el booleano: el binario se sirve por `GET /api/marca/logo`, no aquí.
        "logo": ajuste.logo_bin is not None,
        "logoVersion": logo_version,
    }


def ensamblar_contenido(db: Session, idioma: str, portal_id: str) -> dict:
    """Devuelve un `ContenidoIdioma` para el idioma **del portal**, espejo de
    `obtenerContenido(idioma)`.

    Todo se filtra por `portal_id`: el portal es la unidad de aislamiento y el contenido
    de un portal nunca se mezcla con el de otro. El `portal_id` lo resuelve el servidor a
    partir del host (nunca del cliente), no llega en el cuerpo ni en la query.
    """
    categorias = []
    for c in db.query(Categoria).filter(Categoria.portal_id == portal_id).order_by(Categoria.orden).all():
        tr = _traduccion(c, idioma)
        if tr is None:
            continue
        categorias.append({"id": c.id, "slug": tr.slug, "nombre": tr.nombre, "icono": c.icono})

    articulos = []
    for a in db.query(Articulo).filter(Articulo.portal_id == portal_id).order_by(Articulo.orden).all():
        tr = _traduccion(a, idioma)
        if tr is None:
            continue
        articulos.append(
            {
                "id": a.id,
                "slug": tr.slug,
                "titulo": tr.titulo,
                "categoria": a.categoria_id,
                "actualizado": a.actualizado.isoformat(),
                "minutosLectura": a.minutos_lectura,
                "destacado": a.destacado,
                "parrafos": tr.parrafos,
                "howTo": tr.how_to,
                "nota": tr.nota,
                "faq": tr.faq,
                "relacionados": [r.relacionado_id for r in a.relacionados],
            }
        )

    conv = (
        db.query(Conversacion)
        .filter(Conversacion.portal_id == portal_id, Conversacion.idioma == idioma)
        .first()
    )
    conversacion = conv.mensajes if conv else []

    metricas = [
        {"clave": m.clave, "valor": m.valor}
        for m in db.query(Metrica)
        .filter(Metrica.portal_id == portal_id, Metrica.idioma == idioma)
        .order_by(Metrica.orden)
        .all()
    ]

    # `preguntasSinResolver` NO viaja aquí: es el texto literal de lo que escriben
    # las personas usuarias y puede contener datos personales. Se sirve solo por
    # `/api/admin/preguntas-sin-resolver`, tras la dependencia de nivel.
    return {
        # El nombre de marca y la paleta los ve todo visitante anónimo: son públicos.
        # El acento y las paradas del banner alimentan los tokens CSS en SSR.
        "empresa": obtener_empresa(db, portal_id),
        **obtener_marca(db, portal_id),
        "categorias": categorias,
        "articulos": articulos,
        "conversacion": conversacion,
        "metricas": metricas,
    }


def documento_a_dict(d: Documento) -> dict:
    """Serializa un documento para el panel. NUNCA expone binario ni embeddings."""
    return {
        "id": d.id,
        "nombre": d.nombre,
        "mime": d.mime,
        "idioma": d.idioma,
        "estado": d.estado,
        "errorDetalle": d.error_detalle,
        "bytes": d.bytes,
        "creado": d.created_at.isoformat() if d.created_at is not None else "",
        "actualizado": d.updated_at.isoformat() if d.updated_at is not None else "",
    }


def usuario_a_dict(u: AdminUser) -> dict:
    """Serializa un usuario para el panel de Administrador. Nunca expone el hash."""
    return {
        "id": u.id,
        "email": u.email,
        "nivel": u.nivel,
        "activo": u.activo,
        "creado": u.created_at.isoformat() if u.created_at is not None else "",
    }


def articulo_a_admin_dict(a: Articulo) -> dict:
    """Serializa un artículo con sus dos idiomas para editarlo en el panel."""

    def trad_dict(idioma: str) -> dict:
        t = _traduccion(a, idioma)
        return {
            "slug": t.slug,
            "titulo": t.titulo,
            "parrafos": t.parrafos,
            "howTo": t.how_to,
            "nota": t.nota,
            "faq": t.faq,
        }

    return {
        "id": a.id,
        "categoria": a.categoria_id,
        "actualizado": a.actualizado.isoformat(),
        "minutosLectura": a.minutos_lectura,
        "destacado": a.destacado,
        "relacionados": [r.relacionado_id for r in a.relacionados],
        "es": trad_dict("es"),
        "pt": trad_dict("pt"),
    }


def categoria_a_admin_dict(c: Categoria) -> dict:
    """Serializa una categoría con sus dos idiomas para gestionarla en el panel."""

    def trad_dict(idioma: str) -> dict:
        t = _traduccion(c, idioma)
        return {"slug": t.slug, "nombre": t.nombre}

    return {
        "id": c.id,
        "icono": c.icono,
        "orden": c.orden,
        "es": trad_dict("es"),
        "pt": trad_dict("pt"),
    }


def aplicar_datos_categoria(c: Categoria, datos, *, incluir_id: bool, portal_id: str) -> None:
    """Vuelca los campos de un `CategoriaIn`/`CategoriaUpdateIn` en la entidad ORM.

    Atómico bilingüe: escribe siempre ambas traducciones (es+pt). El id es la clave
    estable entre idiomas y se normaliza en el servidor (autoridad), como en artículos.
    El `portal_id` lo fija el servidor (nunca el cliente) en la categoría y en cada
    traducción, para que el aislamiento por portal se sostenga también en la escritura.
    """
    if incluir_id:
        c.id = normalizar_slug(datos.id)
    c.portal_id = portal_id
    c.icono = datos.icono
    c.orden = datos.orden

    c.traducciones = []
    for idioma in IDIOMAS:
        t = getattr(datos, idioma)
        c.traducciones.append(
            CategoriaTraduccion(
                idioma=idioma,
                portal_id=portal_id,
                slug=normalizar_slug(t.slug),
                nombre=t.nombre,
            )
        )


def pregunta_a_dict(p: PreguntaSinResolver) -> dict:
    """Serializa una pregunta sin resolver para el panel interno."""
    return {
        "id": p.id,
        "idioma": p.idioma,
        "pregunta": p.pregunta,
        "veces": p.veces,
        "similitud": p.similitud,
        # ISO, para el atributo `datetime` de `<time>` en el panel.
        "fecha": p.fecha.isoformat(),
        "estado": p.estado,
    }


def aplicar_datos_articulo(a: Articulo, datos, *, incluir_id: bool, portal_id: str) -> None:
    """Vuelca los campos de un `ArticuloIn`/`ArticuloUpdateIn` en la entidad ORM.

    El `portal_id` lo fija el servidor (nunca el cliente) en el artículo y en cada
    traducción, para sostener el aislamiento por portal también en la escritura.
    """
    if incluir_id:
        # El id es la clave estable entre idiomas: se normaliza en el servidor
        # (autoridad) igual que en el cliente, no se confía en el valor crudo.
        a.id = normalizar_slug(datos.id)
    a.portal_id = portal_id
    a.categoria_id = datos.categoria
    # La fecha de actualización la sella el servidor a hoy en cada guardado (crear o
    # editar); no se confía en el valor del cliente, que solo lo muestra de lectura.
    a.actualizado = date.today()
    a.minutos_lectura = datos.minutosLectura
    a.destacado = datos.destacado

    a.relacionados = [
        ArticuloRelacionado(relacionado_id=rid, orden=i) for i, rid in enumerate(datos.relacionados)
    ]

    a.traducciones = []
    for idioma in IDIOMAS:
        t = getattr(datos, idioma)
        a.traducciones.append(
            ArticuloTraduccion(
                idioma=idioma,
                portal_id=portal_id,
                slug=normalizar_slug(t.slug),
                titulo=t.titulo,
                parrafos=t.parrafos,
                how_to=t.howTo.model_dump(),
                nota=t.nota,
                faq=[f.model_dump() for f in t.faq],
            )
        )
