"""Sondeo de salud de los proveedores de IA por rol.

Responde a una pregunta que hasta ahora solo se podía contestar leyendo los logs
del servidor: cuando el chat degrada a `escalar` o una sugerencia devuelve 502,
¿el proveedor está caído, sin saldo, con la clave revocada, o es un bug propio?

Cada rol (`chat`, `traduccion`, `embeddings`) se sondea contra el proveedor que
tiene asignado en `ConfigIA`, con la llamada **más barata** que distinga las
causas. Para DeepSeek existe `GET /user/balance`, que es gratuito y separa
«clave inválida» (401) de «sin saldo» — justo el par que se confunde desde fuera.

Reglas de diseño:

- **Bajo demanda**, nunca en cada render del panel: lo dispara un botón. Una
  caché en proceso corta las pulsaciones repetidas.
- **Timeout corto** (`TIMEOUT_SONDEO_SEG`): un proveedor colgado no debe dejar
  colgado el panel; a efectos de diagnóstico, «no contesta en 10 s» ya es la
  respuesta.
- **No se devuelve nunca el texto crudo del proveedor** ni la clave: solo un
  estado clasificado y un detalle corto redactado aquí. El mensaje original va
  al log, donde ya lo dejan `app.main` y `app.chat`.
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import ConfigIA
from app.rag import EMBEDDING_MODELO, URL_BASE_EMBEDDINGS
from app.servicios_ia import (
    CONFIG_IA_ID,
    PROVEEDOR_CHAT_POR_DEFECTO,
    PROVEEDOR_EMBEDDINGS_POR_DEFECTO,
    PROVEEDOR_TRADUCCION_POR_DEFECTO,
    URL_BASE_DEEPSEEK,
    ProveedorNoConfigurado,
    _clave_del_proveedor,
)

logger = logging.getLogger(__name__)

# Estados posibles de un rol. `credenciales` y `saldo` son los dos que importa
# separar: ambos dan 502 en el panel pero se arreglan de forma distinta (rotar la
# clave vs. recargar la cuenta).
EstadoSalud = Literal["ok", "sin_clave", "credenciales", "saldo", "timeout", "error"]

ROLES: tuple[str, ...] = ("chat", "traduccion", "embeddings")

# Timeout del sondeo. Deliberadamente corto: esto es un diagnóstico interactivo,
# no una llamada de producto. Si el proveedor no contesta en este plazo, ese
# silencio ya es el resultado que interesa.
TIMEOUT_SONDEO_SEG = 10.0

# Vida de la caché en proceso. Evita que pulsar «Comprobar» repetidamente
# martillee a los proveedores (y, con Voyage, gaste tokens de embedding).
TTL_CACHE_SEG = 60.0

# Cadena constante para el sondeo de embeddings: es el sondeo más barato posible
# que aun así ejercita autenticación, modelo y cuota de verdad.
_SONDA_EMBEDDINGS = "ping"


@dataclass(frozen=True)
class SaludRol:
    rol: str
    proveedor: str
    estado: EstadoSalud
    detalle: str
    # ISO 8601 en UTC, como el resto de marcas de tiempo del contrato.
    comprobado_en: str


def _ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Caché por proveedor -> (instante, estado, detalle, marca ISO). La clave es el
# proveedor y NO el rol porque el sondeo solo depende del proveedor y su clave:
# con `chat` y `traduccion` apuntando ambos a DeepSeek (configuración habitual),
# indexar por rol duplicaba la llamada saliente en cada pulsación.
_cache: dict[str, tuple[float, EstadoSalud, str, str]] = {}


def limpiar_cache() -> None:
    """Vacía la caché del sondeo (los tests la usan para aislarse entre casos)."""
    _cache.clear()


def _proveedor_de(config: ConfigIA | None, rol: str) -> str:
    """Proveedor efectivo del rol, con el mismo criterio de default que usan las
    fábricas de `servicios_ia` (campo NULL o fila ausente -> default del rol)."""
    if rol == "chat":
        return (config.proveedor_chat if config is not None else None) or PROVEEDOR_CHAT_POR_DEFECTO
    if rol == "traduccion":
        return (
            config.proveedor_traduccion if config is not None else None
        ) or PROVEEDOR_TRADUCCION_POR_DEFECTO
    return (
        config.proveedor_embeddings if config is not None else None
    ) or PROVEEDOR_EMBEDDINGS_POR_DEFECTO


def _clasificar_http(codigo: int) -> tuple[EstadoSalud, str]:
    """Traduce el código HTTP del proveedor al par (estado, detalle) que ve el panel."""
    if codigo in (401, 403):
        return "credenciales", "El proveedor rechazó la clave (revocada o incorrecta)."
    if codigo == 402:
        return "saldo", "La cuenta del proveedor no tiene saldo suficiente."
    if codigo == 429:
        return "error", "El proveedor está limitando las peticiones (cuota o ritmo)."
    return "error", f"El proveedor respondió con un error HTTP {codigo}."


def _get_json(url: str, clave: str) -> tuple[EstadoSalud, str]:
    """`GET` autenticado con Bearer. Devuelve el par (estado, detalle) clasificado."""
    peticion = urllib.request.Request(url, headers={"Authorization": f"Bearer {clave}"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SONDEO_SEG):
            return "ok", "El proveedor responde correctamente."
    except urllib.error.HTTPError as exc:
        return _clasificar_http(exc.code)
    except TimeoutError:
        return "timeout", f"El proveedor no respondió en {int(TIMEOUT_SONDEO_SEG)} s."
    except urllib.error.URLError as exc:
        # Incluye DNS y conexión rechazada; también envuelve `TimeoutError` en
        # algunas versiones, de ahí la comprobación del motivo.
        if isinstance(exc.reason, TimeoutError):
            return "timeout", f"El proveedor no respondió en {int(TIMEOUT_SONDEO_SEG)} s."
        return "error", "No se pudo contactar con el proveedor."


def _sondear_deepseek(clave: str) -> tuple[EstadoSalud, str]:
    """`GET /user/balance`: gratuito y, a diferencia de una completion, distingue
    401 (clave inválida) de 402 (sin saldo) sin gastar tokens."""
    return _get_json(f"{URL_BASE_DEEPSEEK}/user/balance", clave)


def _sondear_anthropic(clave: str) -> tuple[EstadoSalud, str]:
    """`GET /v1/models`: gratuito y valida la clave. Usa cabeceras propias de
    Anthropic (`x-api-key` + `anthropic-version`), no Bearer."""
    peticion = urllib.request.Request(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": clave, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SONDEO_SEG):
            return "ok", "El proveedor responde correctamente."
    except urllib.error.HTTPError as exc:
        return _clasificar_http(exc.code)
    except TimeoutError:
        return "timeout", f"El proveedor no respondió en {int(TIMEOUT_SONDEO_SEG)} s."
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            return "timeout", f"El proveedor no respondió en {int(TIMEOUT_SONDEO_SEG)} s."
        return "error", "No se pudo contactar con el proveedor."


def _sondear_embeddings(clave: str) -> tuple[EstadoSalud, str]:
    """Embedding de una cadena de un token. No hay endpoint gratuito equivalente
    en Voyage/OpenAI, pero el coste de una sonda de un token es despreciable y a
    cambio ejercita clave, modelo y cuota de verdad."""
    try:
        from openai import OpenAI
    except ImportError:  # pragma: no cover - depende del entorno
        return "error", "El SDK de OpenAI (para embeddings) no está instalado."
    cliente = OpenAI(api_key=clave, base_url=URL_BASE_EMBEDDINGS, timeout=TIMEOUT_SONDEO_SEG)
    try:
        cliente.embeddings.create(model=EMBEDDING_MODELO, input=[_SONDA_EMBEDDINGS])
    except Exception as exc:  # el SDK envuelve el HTTP; se clasifica por `status_code`
        codigo = getattr(exc, "status_code", None)
        if isinstance(codigo, int):
            return _clasificar_http(codigo)
        if "timeout" in type(exc).__name__.lower():
            return "timeout", f"El proveedor no respondió en {int(TIMEOUT_SONDEO_SEG)} s."
        return "error", "No se pudo contactar con el proveedor."
    return "ok", "El proveedor responde correctamente."


def _sondear(proveedor: str, clave: str) -> tuple[EstadoSalud, str]:
    if proveedor == "deepseek":
        return _sondear_deepseek(clave)
    if proveedor == "anthropic":
        return _sondear_anthropic(clave)
    if proveedor in ("voyage", "openai"):
        return _sondear_embeddings(clave)
    return "error", f"No hay sondeo implementado para el proveedor '{proveedor}'."


def comprobar_rol(db: Session, rol: str, config: ConfigIA | None) -> SaludRol:
    """Sondea el proveedor asignado a `rol`, sirviendo de la caché si sigue fresca."""
    proveedor = _proveedor_de(config, rol)
    ahora = time.time()

    en_cache = _cache.get(proveedor)
    if en_cache is not None and ahora - en_cache[0] < TTL_CACHE_SEG:
        _, estado, detalle, marca = en_cache
        return SaludRol(
            rol=rol, proveedor=proveedor, estado=estado, detalle=detalle, comprobado_en=marca
        )

    try:
        clave = _clave_del_proveedor(db, proveedor)
    except ProveedorNoConfigurado:
        # No se cachea: en cuanto SuperAdmin guarde la clave, el siguiente sondeo
        # debe reflejarlo sin esperar al TTL.
        return SaludRol(
            rol=rol,
            proveedor=proveedor,
            estado="sin_clave",
            detalle="No hay clave de API guardada para este proveedor.",
            comprobado_en=_ahora_iso(),
        )

    estado, detalle = _sondear(proveedor, clave)
    if estado != "ok":
        logger.warning("Salud IA: rol=%s proveedor=%s estado=%s", rol, proveedor, estado)

    marca = _ahora_iso()
    _cache[proveedor] = (ahora, estado, detalle, marca)
    return SaludRol(
        rol=rol, proveedor=proveedor, estado=estado, detalle=detalle, comprobado_en=marca
    )


def comprobar_todos(db: Session) -> list[SaludRol]:
    """Sondea los tres roles. Secuencial a propósito: son tres llamadas cortas y
    normalmente golpean a uno o dos proveedores distintos."""
    config = db.get(ConfigIA, CONFIG_IA_ID)
    return [comprobar_rol(db, rol, config) for rol in ROLES]
