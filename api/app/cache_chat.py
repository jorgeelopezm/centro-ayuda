"""Caché LRU + TTL en memoria del proceso para respuestas del chat.

Diseño (cambio OpenSpec `chat-evals-brevedad-supervision`, spec
`chat-generativo-rag` › «Caché de respuesta por portal con revalidación de
citas»):

- **Clave**: `sha256(portal_id | idioma | consulta_normalizada |
  config_ia_version | schema_recuperacion)`. La consulta se normaliza (trim,
  minúsculas, espacios colapsados) para que "¿Cómo cancelo?" y " cómo cancelo "
  compartan entrada.
- **Alcance**: por proceso, no compartida entre workers. Es un warm cache
  parcial en despliegue multi-worker; suficiente para la escala actual y evita
  introducir Redis.
- **Solo `respondida`**: `sin_resultados`, `fuera_de_scope` y `escalar` NO se
  cachean (dependen del estado de la sesión o son baratos de reclasificar).
- **Revalidación**: antes de servir un hit, el caller verifica que cada recurso
  citado (artículo por `slug`+portal, documento por `nombre`+portal) sigue
  existiendo; si no, se invalida la entrada y la consulta ejecuta el pipeline
  completo.

Este módulo es puro estado en memoria: no toca la base ni el proveedor. El
singleton `obtener_cache()` se construye perezosamente desde `settings`; los
tests lo descartan con `reset_para_tests()`.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.config import get_settings

# Bump manual si cambia el contrato del recuperador (top_k, formato de
# fragmentos, umbral por defecto...): la caché queda invalidada implícitamente
# porque la clave cambia. Va aparte de `config_ia_version` porque el recuperador
# no depende del proveedor de LLM.
SCHEMA_RECUPERACION = "v1"

_ESPACIOS = re.compile(r"\s+")


def normalizar_consulta(consulta: str) -> str:
    """Trim, minúsculas y espacios colapsados. Dos formulaciones equivalentes
    de la misma consulta comparten entrada en caché."""
    return _ESPACIOS.sub(" ", (consulta or "").strip().lower())


@dataclass(frozen=True)
class Recurso:
    """Recurso citado por una respuesta cacheada, guardado para revalidar
    existencia antes de servir el hit. `identificador` es `slug` para artículos
    y `nombre` para documentos (los dos campos únicos por portal)."""

    tipo: str  # "articulo" | "documento"
    identificador: str


@dataclass
class EntradaCache:
    """Contenido cacheado (solo veredicto `respondida`).

    `fuentes` viaja como `list[Any]` para no importar `app.chat` desde aquí y
    evitar ciclo de módulos: son objetos `chat.Fuente` que el caller reconstruye
    tal cual en la respuesta.
    """

    veredicto: str
    mensaje: str
    fuentes: list[Any]
    recursos: tuple[Recurso, ...]
    # `time.monotonic()` en el que la entrada vence. Se rellena en `guardar()`
    # cuando el caller lo deja en 0.0.
    expira_en: float


def derivar_clave(
    *,
    portal_id: str,
    idioma: str,
    consulta: str,
    config_ia_version: str,
    schema_recuperacion: str = SCHEMA_RECUPERACION,
) -> str:
    """`sha256` hexadecimal de los cinco componentes.

    Se usa `\\x1f` (unit separator, ASCII 31) como delimitador: es un byte que
    no aparece en texto normal, así que `"a" + "b"` y `"ab" + ""` no colisionan.
    """
    entrada = "\x1f".join(
        [
            portal_id,
            idioma,
            normalizar_consulta(consulta),
            config_ia_version,
            schema_recuperacion,
        ]
    ).encode("utf-8")
    return hashlib.sha256(entrada).hexdigest()


class CacheChat:
    """LRU + TTL en memoria del proceso.

    No es thread-safe: uvicorn+FastAPI reciben cada request en su propio task
    del event loop (GIL); `obtener`/`guardar` son de complejidad constante y no
    ceden control. Si en el futuro se corre con un worker multi-hilo hay que
    envolver las operaciones con un `Lock`.
    """

    def __init__(self, *, capacidad: int, ttl_seg: int) -> None:
        self._capacidad = max(0, int(capacidad))
        self._ttl_seg = max(0, int(ttl_seg))
        self._data: OrderedDict[str, EntradaCache] = OrderedDict()

    def obtener(self, clave: str, ahora: float | None = None) -> EntradaCache | None:
        """Devuelve la entrada viva o `None`. Si expiró, la borra. Un hit vivo
        se mueve al final (LRU: más reciente)."""
        if ahora is None:
            ahora = time.monotonic()
        entrada = self._data.get(clave)
        if entrada is None:
            return None
        if entrada.expira_en <= ahora:
            self._data.pop(clave, None)
            return None
        self._data.move_to_end(clave)
        return entrada

    def guardar(
        self,
        clave: str,
        entrada: EntradaCache,
        ahora: float | None = None,
    ) -> None:
        """Guarda la entrada. Si `entrada.expira_en <= 0.0`, se calcula
        `ahora + ttl_seg`. Aplica LRU: si supera la capacidad, desaloja la más
        antigua."""
        if self._capacidad == 0:
            return
        if ahora is None:
            ahora = time.monotonic()
        if entrada.expira_en <= 0.0:
            entrada.expira_en = ahora + self._ttl_seg
        self._data[clave] = entrada
        self._data.move_to_end(clave)
        while len(self._data) > self._capacidad:
            self._data.popitem(last=False)

    def invalidar(self, clave: str) -> None:
        """Borra la entrada si existe."""
        self._data.pop(clave, None)

    def invalidar_si_recursos_faltan(
        self,
        clave: str,
        entrada: EntradaCache,
        recurso_check: Callable[[Recurso], bool],
    ) -> bool:
        """Ejecuta `recurso_check` sobre cada recurso citado por la entrada. Si
        alguno devuelve `False`, invalida la clave y devuelve `True` (el caller
        debe re-ejecutar el pipeline). Si todos siguen presentes devuelve
        `False` y la entrada sigue viva."""
        for recurso in entrada.recursos:
            if not recurso_check(recurso):
                self.invalidar(clave)
                return True
        return False

    def __len__(self) -> int:
        return len(self._data)

    def reset(self) -> None:
        """Vacía el diccionario (para tests o mantenimiento manual)."""
        self._data.clear()


# --- Singleton por proceso ---------------------------------------------------

_cache: CacheChat | None = None


def obtener_cache() -> CacheChat:
    """Devuelve el singleton, construyéndolo perezosamente con los settings
    actuales. `reset_para_tests()` lo descarta para que la siguiente llamada lo
    re-lea (útil cuando un test sobrescribe `chat_cache_*` por monkeypatch)."""
    global _cache
    if _cache is None:
        s = get_settings()
        _cache = CacheChat(
            capacidad=s.chat_cache_max_entradas,
            ttl_seg=s.chat_cache_ttl_seg,
        )
    return _cache


def reset_para_tests() -> None:
    """Descarta el singleton (los tests lo re-construyen desde settings)."""
    global _cache
    _cache = None
