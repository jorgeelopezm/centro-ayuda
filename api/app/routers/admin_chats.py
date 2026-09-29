"""Endpoints de supervisión de chats para el panel (spec `supervision-chats`).

Tres endpoints, todos con nivel ≥ Editor y filtrados por el `portal_id`
resuelto del host (aislamiento multi-tenant en el servidor):

- `GET /api/admin/chats` — lista paginada agregada por `chat_id`, ordenada
  por última actividad desc. Filtros opcionales: `veredicto`, `desde`, `hasta`,
  `limit` (default 50, tope 200) y `cursor` (opaco).
- `GET /api/admin/chats/metricas` — tres KPIs del periodo (default: 30 días).
  La respuesta se cachea en memoria del proceso 60 s por
  `(portal_id, desde, hasta)`.
- `GET /api/admin/chats/{chat_id}` — hilo completo del chat pedido.

**Aislamiento por portal.** El `portal_id` viene del host. SuperAdmin puede
sobreescribirlo con `?portal_id=`; para el resto de niveles ese parámetro se
ignora silenciosamente. Un `chat_id` que no pertenezca al portal efectivo
responde **404** (no 403) para no revelar existencia.

Orden de registro importante: `/metricas` va antes que `/{chat_id}` para que
FastAPI no interprete la ruta fija como un `chat_id` opaco.
"""

from __future__ import annotations

import base64
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import admin_actual, portal_actual, requiere_nivel
from app.models import AdminUser, ChatInteraccion, NivelAcceso, Portal
from app.schemas import (
    ChatDetalleOut,
    ChatListaOut,
    ChatMetricasOut,
)

# La supervisión es una función de producto: se abre a Editor (nivel 2).
# Administrador y SuperAdmin la heredan por comparación numérica.
router = APIRouter(
    prefix="/api/admin/chats",
    tags=["admin", "chats"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.EDITOR))],
)

# Cotas del listado paginado. `LIMIT_MAXIMO` vive en el server (no en el
# cliente) para acotar el gasto de la agregación aunque se pida un valor mayor.
LIMIT_DEFECTO = 50
LIMIT_MAXIMO = 200

# TTL de la caché en memoria del endpoint de métricas. Un refresh cada
# navegación por el panel no debe recomputar la agregación completa.
METRICAS_TTL_SEG = 60

# Rango por defecto cuando el cliente no envía `desde/hasta`.
METRICAS_RANGO_DEFECTO_DIAS = 30


# --- Caché en memoria del endpoint de métricas ------------------------------
# Vive por proceso (como `sesiones_chat` y `cache_chat`); en un despliegue
# multi-worker es un warm cache parcial y basta a la escala actual. Redis
# quedaría para el día que haya varias instancias del panel.

_cache_metricas: dict[tuple[str, str, str], tuple[float, dict]] = {}
# Reloj de la caché. Se apunta a `time.monotonic` porque los tests no necesitan
# inyectar uno propio: `reset_cache_metricas_para_tests()` alcanza para todos
# los escenarios de la spec (aislar hit/miss dentro de un mismo test).
_reloj = time.monotonic


def reset_cache_metricas_para_tests() -> None:
    """Vacía la caché de métricas entre tests. NO exportar fuera de tests."""
    _cache_metricas.clear()


# --- Helpers compartidos ----------------------------------------------------


def _portal_id_efectivo(
    admin: AdminUser,
    portal: Portal,
    portal_id_query: str | None,
) -> str:
    """Portal sobre el que operar.

    SuperAdmin puede sobreescribir por `?portal_id=`; para Editor y
    Administrador el parámetro se ignora silenciosamente (no error) y manda
    el portal resuelto del host. Devolver 400 al pasarlo delataría al cliente
    que existe la opción de sobreescritura y sería ruido; la política es la
    misma del resto de la API multi-tenant. Un `portal_id` de SuperAdmin que
    no sea un UUID válido se ignora igual (mismo silencio) en vez de romper
    la petición: `Portal.id` es un `uuid.UUID` desde la migración `0012`, así
    que ya no vale cualquier cadena como antes (cuando `id == slug`).
    """
    if portal_id_query and admin.nivel >= NivelAcceso.SUPERADMIN.value:
        try:
            uuid.UUID(portal_id_query)
        except ValueError:
            pass
        else:
            return portal_id_query
    # `str(...)`: `Portal.id` es un `uuid.UUID`; el resto de esta ruta (clave de
    # caché, filtros y los esquemas de salida `portal_id: str`) asume texto.
    return str(portal.id)


def _parsear_iso(cadena: str | None, campo: str) -> datetime | None:
    """Fecha ISO 8601 → `datetime` aware (UTC si no lleva offset).

    Acepta las formas comunes: `AAAA-MM-DD`, `AAAA-MM-DDTHH:MM:SS`,
    `AAAA-MM-DDTHH:MM:SS+00:00` y sufijo `Z` (que `fromisoformat` no aceptaba
    hasta Python 3.11; se traduce a `+00:00`). Un cliente que mande el `+`
    del offset sin URL-encodear llega con un espacio en su lugar (regla del
    query string): lo reconvertimos a `+` para no penalizarlo con un 422.
    """
    if not cadena:
        return None
    normalizada = cadena.replace("Z", "+00:00")
    # Solo el espacio ANTES del offset (`... 00:00`) — el separador T ya vino
    # como `T` desde el cliente y el ISO acepta también un espacio ahí, así
    # que este `rsplit` toca únicamente el offset colado como espacio.
    if len(normalizada) >= 6 and normalizada[-6] == " " and normalizada[-3] == ":":
        normalizada = normalizada[:-6] + "+" + normalizada[-5:]
    try:
        dt = datetime.fromisoformat(normalizada)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Formato de fecha inválido en «{campo}»: usar ISO 8601",
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _codificar_cursor(offset: int) -> str:
    """Cursor opaco de paginación (offset ocultado en base64 URL-safe).

    El offset basta a la escala del panel: la agregación por `chat_id` se hace
    en memoria y N raramente pasa de las miles de filas por portal. Si un día
    esto duele, se sustituye por keyset (`(ultima_en, chat_id)`) sin cambiar
    el contrato — el cursor es opaco por definición.
    """
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii").rstrip("=")


def _decodificar_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        offset = int(base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Cursor inválido"
        ) from exc
    if offset < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cursor inválido")
    return offset


def _interaccion_a_dict(f: ChatInteraccion) -> dict:
    """Serializa una fila `chat_interaccion` para `ChatInteraccionOut`."""
    return {
        "id": f.id,
        "chat_id": f.chat_id,
        # `str(...)`: `ChatInteraccion.portal_id` es un `uuid.UUID`; el esquema de
        # salida lo espera como texto.
        "portal_id": str(f.portal_id),
        "turno": f.turno,
        "idioma": f.idioma,
        "consulta": f.consulta,
        "veredicto": f.veredicto,
        "mensaje": f.mensaje,
        "citas": list(f.citas or []),
        "razon_escalamiento": f.razon_escalamiento,
        "latencia_ms": f.latencia_ms,
        "tokens_entrada": f.tokens_entrada,
        "tokens_salida": f.tokens_salida,
        "proveedor": f.proveedor,
        "modelo": f.modelo,
        "creado_en": f.creado_en.isoformat() if f.creado_en is not None else "",
    }


# --- Métricas (registrado ANTES de `/{chat_id}` para no chocar) -------------


@router.get("/metricas", response_model=ChatMetricasOut)
def metricas(
    desde: str | None = Query(default=None),
    hasta: str | None = Query(default=None),
    portal_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
    admin: AdminUser = Depends(admin_actual),
) -> dict:
    """Tres KPIs agregados por `chat_id` para el portal y el rango.

    La agregación se hace en Python (dict) para no depender de sintaxis SQL
    específica de Postgres: los tests corren en SQLite y esta ruta también
    debe funcionar allí. A la escala del panel (miles de filas) es de sobra.
    """
    portal_efectivo = _portal_id_efectivo(admin, portal, portal_id)
    dt_hasta = _parsear_iso(hasta, "hasta") or datetime.now(timezone.utc)
    dt_desde = _parsear_iso(desde, "desde") or (
        dt_hasta - timedelta(days=METRICAS_RANGO_DEFECTO_DIAS)
    )

    clave = (portal_efectivo, dt_desde.isoformat(), dt_hasta.isoformat())
    ahora = _reloj()
    hit = _cache_metricas.get(clave)
    if hit is not None and (ahora - hit[0]) < METRICAS_TTL_SEG:
        return hit[1]

    filas = (
        db.query(
            ChatInteraccion.chat_id,
            ChatInteraccion.creado_en,
            ChatInteraccion.veredicto,
        )
        .filter(
            # `uuid.UUID(...)`: `ChatInteraccion.portal_id` es `uuid.UUID`
            # (columna `Uuid`); SQLAlchemy exige el tipo nativo al enlazar.
            ChatInteraccion.portal_id == uuid.UUID(portal_efectivo),
            ChatInteraccion.creado_en >= dt_desde,
            ChatInteraccion.creado_en < dt_hasta,
        )
        .order_by(ChatInteraccion.chat_id, ChatInteraccion.creado_en.desc())
        .all()
    )
    ultimos: dict[str, str] = {}
    for chat_id_row, _creado_en, veredicto in filas:
        # Ordenado DESC por `creado_en`: el primer visto de cada chat es su
        # último turno. Se ignora el resto.
        if chat_id_row not in ultimos:
            ultimos[chat_id_row] = veredicto

    total = len(ultimos)
    respondida = sum(1 for v in ultimos.values() if v == "respondida")
    escalados = sum(1 for v in ultimos.values() if v == "escalar")
    pct = round((respondida / total) * 100.0, 2) if total > 0 else 0.0

    salida = {
        "chats_total": total,
        "chats_respondidos_con_cita_pct": pct,
        "chats_escalados": escalados,
        "desde": dt_desde.isoformat(),
        "hasta": dt_hasta.isoformat(),
    }
    _cache_metricas[clave] = (ahora, salida)
    return salida


# --- Listado agregado por chat_id -------------------------------------------


_VeredictoFiltro = Literal["respondida", "sin_resultados", "fuera_de_scope", "escalar"]


@router.get("", response_model=ChatListaOut)
def listar(
    veredicto: _VeredictoFiltro | None = Query(default=None),
    desde: str | None = Query(default=None),
    hasta: str | None = Query(default=None),
    limit: int = Query(default=LIMIT_DEFECTO, ge=1, le=LIMIT_MAXIMO),
    cursor: str | None = Query(default=None),
    portal_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
    admin: AdminUser = Depends(admin_actual),
) -> dict:
    """Chats agregados por `chat_id`, ordenados por última actividad desc.

    Agregamos en Python por portabilidad (SQLite tests / Postgres producción):
    el volumen del panel lo aguanta y la lógica queda a la vista. Si crece,
    se sustituye por una CTE en el ORM sin cambiar el contrato.
    """
    portal_efectivo = _portal_id_efectivo(admin, portal, portal_id)
    dt_desde = _parsear_iso(desde, "desde")
    dt_hasta = _parsear_iso(hasta, "hasta")
    offset = _decodificar_cursor(cursor)

    # `uuid.UUID(...)`: `ChatInteraccion.portal_id` es `uuid.UUID` (columna
    # `Uuid`); SQLAlchemy exige el tipo nativo al enlazar.
    consulta = db.query(ChatInteraccion).filter(
        ChatInteraccion.portal_id == uuid.UUID(portal_efectivo)
    )
    if dt_desde is not None:
        consulta = consulta.filter(ChatInteraccion.creado_en >= dt_desde)
    if dt_hasta is not None:
        consulta = consulta.filter(ChatInteraccion.creado_en < dt_hasta)
    filas = consulta.order_by(
        ChatInteraccion.chat_id, ChatInteraccion.turno
    ).all()

    agregados: dict[str, dict] = {}
    for f in filas:
        entrada = agregados.setdefault(
            f.chat_id,
            {
                "chat_id": f.chat_id,
                "portal_id": f.portal_id,
                "turnos": 0,
                "idioma": f.idioma,
                "ultimo_veredicto": f.veredicto,
                "creado_en": f.creado_en,
                "ultima_en": f.creado_en,
            },
        )
        entrada["turnos"] += 1
        # `creado_en` puede ser NULL si un test lo inserta antes de flush; se
        # trata como no-comparable manteniendo el valor actual.
        if f.creado_en is not None and (
            entrada["ultima_en"] is None or f.creado_en > entrada["ultima_en"]
        ):
            entrada["ultima_en"] = f.creado_en
            entrada["idioma"] = f.idioma
            entrada["ultimo_veredicto"] = f.veredicto
        if f.creado_en is not None and (
            entrada["creado_en"] is None or f.creado_en < entrada["creado_en"]
        ):
            entrada["creado_en"] = f.creado_en

    items = list(agregados.values())
    if veredicto is not None:
        items = [it for it in items if it["ultimo_veredicto"] == veredicto]
    # Orden por última actividad desc; desempate por chat_id para ser determinista.
    items.sort(
        key=lambda it: (
            it["ultima_en"] or datetime.min.replace(tzinfo=timezone.utc),
            it["chat_id"],
        ),
        reverse=True,
    )

    pagina = items[offset : offset + limit]
    hay_mas = offset + limit < len(items)
    siguiente = _codificar_cursor(offset + limit) if hay_mas else None

    return {
        "items": [
            {
                "chat_id": it["chat_id"],
                # `str(...)`: `it["portal_id"]` viene de `ChatInteraccion.portal_id`
                # (`uuid.UUID`); el esquema de salida lo espera como texto.
                "portal_id": str(it["portal_id"]),
                "idioma": it["idioma"],
                "turnos": it["turnos"],
                "ultimo_veredicto": it["ultimo_veredicto"],
                "creado_en": it["creado_en"].isoformat() if it["creado_en"] is not None else "",
                "ultima_en": it["ultima_en"].isoformat() if it["ultima_en"] is not None else "",
            }
            for it in pagina
        ],
        "siguiente_cursor": siguiente,
    }


# --- Detalle de un chat -----------------------------------------------------


@router.get("/{chat_id}", response_model=ChatDetalleOut)
def detalle(
    chat_id: str,
    portal_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
    admin: AdminUser = Depends(admin_actual),
) -> dict:
    """Hilo completo del `chat_id` del portal efectivo, ordenado por `turno`.

    Un chat de otro portal o inexistente responde 404 con el mismo mensaje
    (no 403): el filtro por `portal_id` es la barrera de aislamiento y el
    endpoint no distingue entre "no existe" y "no te pertenece" para no
    revelar existencia (misma política que el resto del panel).
    """
    portal_efectivo = _portal_id_efectivo(admin, portal, portal_id)
    filas = (
        db.query(ChatInteraccion)
        .filter(
            ChatInteraccion.chat_id == chat_id,
            # `uuid.UUID(...)`: `ChatInteraccion.portal_id` es `uuid.UUID`
            # (columna `Uuid`); SQLAlchemy exige el tipo nativo al enlazar.
            ChatInteraccion.portal_id == uuid.UUID(portal_efectivo),
        )
        .order_by(ChatInteraccion.turno)
        .all()
    )
    if not filas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat no encontrado")
    return {
        "chat_id": chat_id,
        "portal_id": portal_efectivo,
        "interacciones": [_interaccion_a_dict(f) for f in filas],
    }
