"""Endpoint público del chat con RAG por portal.

`POST /api/{idioma}/chat/consultar` es Anonymous (sin sesión): el chat lo usan
los visitantes del centro de ayuda. La única fuente del tenant es el host de la
petición, resuelto por la dependencia `portal_actual` (`app.deps`). Cualquier
`portal_id` que llegue en el cuerpo se ignora silenciosamente
(`ChatConsultaIn.model_config.extra="ignore"`).

Antes de invocar al pipeline aplica:
- interruptor `CHAT_HABILITADO=false` → 503 "en mantenimiento" (sin proveedor).
- limitador de tasa por IP en memoria (`CHAT_LIMITE_TASA_MIN`).

La respuesta siempre incluye `chat_id`: el emitido si es nuevo, el mismo si el
cliente lo pasó y sigue vivo, o uno nuevo si venció (ver `sesiones_chat`). El
alias entrante `session_id` (contrato anterior) sigue aceptándose durante la
transición; ver `ChatConsultaIn`.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.chat import (
    ConsultaInvalida,
    Turno,
    responder,
    serializar_conversacion,
)
from app.config import get_settings
from app.database import get_db
from app.deps import portal_actual
from app.models import Portal
from app.schemas import ChatConsultaIn, ChatConsultaOut
from app.servicios import IDIOMAS

router = APIRouter(prefix="/api", tags=["chat"])


# --- Limitador de tasa por IP en memoria del proceso -------------------------
# Ventana deslizante: por cada IP se guardan los timestamps de las últimas
# peticiones dentro de la ventana de 60 s; si el conteo supera el umbral, se
# rechaza. Sin librería externa (evita nueva dependencia). Estado se pierde
# entre reinicios y no se comparte entre workers; suficiente para un tenant
# chico single-worker (patrón simétrico al de `sesiones_chat`).
#
# `_MAX_IPS` acota la cardinalidad del dict para que un flujo con muchas IPs
# distintas no crezca sin límite (bomba de memoria trivial). Al superar el
# tope se ejecuta una purga perezosa que elimina las entradas cuyas colas
# quedaron vacías tras descartar los timestamps caducados; si aún así se
# rebasa, se descartan las entradas más antiguas (LRU aproximada por orden de
# inserción de `dict`) hasta bajar del umbral. Ventana de 60 s + purga solo
# cuando toca hace que este overhead sea invisible en la ruta caliente.

_VENTANA_SEG = 60.0
_MAX_IPS = 10_000
_IPS: dict[str, Deque[float]] = defaultdict(deque)


def _reloj_actual() -> float:
    """Reloj del limitador (segundos, monotonic). Se sustituye en tests."""
    return time.monotonic()


_ahora_tasa = _reloj_actual


def inyectar_reloj_tasa(fn) -> None:  # noqa: ANN001 - firma libre para tests
    """Reemplaza el reloj del limitador de tasa (solo para tests)."""
    global _ahora_tasa
    _ahora_tasa = fn


def restaurar_reloj_tasa() -> None:
    global _ahora_tasa
    _ahora_tasa = _reloj_actual


def reset_limitador_para_tests() -> None:
    _IPS.clear()


def _purgar_ips_vencidas(ahora: float) -> None:
    """Elimina entradas cuya cola queda vacía tras descartar timestamps caducados,
    y si el dict aún supera el tope, descarta las entradas más antiguas por
    orden de inserción (LRU aproximada). Solo se llama cuando `len(_IPS)` roza
    el tope: no gasta tiempo en la ruta caliente."""
    for ip in list(_IPS.keys()):
        cola = _IPS[ip]
        while cola and (ahora - cola[0]) > _VENTANA_SEG:
            cola.popleft()
        if not cola:
            del _IPS[ip]
    exceso = len(_IPS) - _MAX_IPS
    if exceso > 0:
        for ip in list(_IPS.keys())[:exceso]:
            del _IPS[ip]


def _ip_permitida(ip: str, limite_por_min: int) -> bool:
    """Devuelve True si la IP puede emitir una consulta más en la ventana."""
    ahora = _ahora_tasa()
    if len(_IPS) >= _MAX_IPS and ip not in _IPS:
        _purgar_ips_vencidas(ahora)
    cola = _IPS[ip]
    # Descarta los timestamps fuera de la ventana.
    while cola and (ahora - cola[0]) > _VENTANA_SEG:
        cola.popleft()
    if len(cola) >= limite_por_min:
        return False
    cola.append(ahora)
    return True


def _peer_confiable(request: Request) -> bool:
    """`True` si el salto inmediato al backend está en `proxies_confiables`.

    Espeja `deps._peer_confiable` (misma política, incluida la normalización
    `::ffff:X` → `X` para IPv4-mapeada-en-IPv6 que devuelve uvicorn en
    Windows dual-stack) pero se duplica aquí para no crear dependencia
    inversa `routers → deps` (los tests inyectan settings por env). Cuando
    `request.client is None` (TestClient en proceso), se considera confiable."""
    if request.client is None:
        return True
    peer = request.client.host
    if peer.startswith("::ffff:"):
        peer = peer[len("::ffff:") :]
    return peer in get_settings().proxies_confiables_set


def _ip_de(request: Request) -> str:
    """IP del cliente para el limitador de tasa.

    `X-Forwarded-For` solo se acepta cuando el peer inmediato está en la lista
    de proxies confiables. Sin esa comprobación, cualquier cliente podría
    saltarse el rate limit fabricando IPs distintas en la cabecera, o al revés,
    colapsar toda la audiencia bajo la IP del proxy (que veía siempre el
    backend, `127.0.0.1`) y disparar denegaciones cruzadas. Se toma el primer
    valor de la lista (el del cliente, no los saltos intermedios)."""
    if _peer_confiable(request):
        reenviado = request.headers.get("x-forwarded-for")
        if reenviado:
            return reenviado.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "desconocida"


# --- Endpoint ---------------------------------------------------------------


@router.post(
    "/{idioma}/chat/consultar",
    response_model=ChatConsultaOut,
    response_model_exclude_none=True,
)
def consultar_chat(
    idioma: str,
    cuerpo: ChatConsultaIn,
    request: Request,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> ChatConsultaOut:
    if idioma not in IDIOMAS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Idioma no encontrado")

    settings = get_settings()

    if not settings.chat_habilitado:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El chat está en mantenimiento. Vuelve a intentarlo más tarde.",
        )

    ip = _ip_de(request)
    if not _ip_permitida(ip, settings.chat_limite_tasa_min):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Demasiadas consultas. Espera un momento antes de intentar de nuevo.",
        )

    historial = [Turno(rol=t.rol, texto=t.texto) for t in cuerpo.historial]

    try:
        respuesta = responder(
            consulta=cuerpo.consulta,
            idioma=idioma,
            historial=historial,
            # `str(...)`: `Portal.id` es un `uuid.UUID`; todo el pipeline del chat
            # (caché, recuperador, persistencia) trata `portal_id` como texto.
            portal_id=str(portal.id),
            chat_id=cuerpo.chat_id_efectivo,
            solicitar_soporte=cuerpo.solicitar_soporte,
            db=db,
        )
    except ConsultaInvalida as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return ChatConsultaOut(
        veredicto=respuesta.veredicto,
        mensaje=respuesta.mensaje,
        chat_id=respuesta.chat_id,
        fuentes=[
            {"n": f.n, "tipo": f.tipo, "titulo": f.titulo, "slug": f.slug}
            for f in respuesta.fuentes
        ],
        razon=respuesta.razon,
        conversacion=serializar_conversacion(respuesta.conversacion),
    )
