"""Sesiones de chat efímeras en memoria del proceso.

Cada consulta del chat lleva un `session_id` opaco (UUID). El servidor emite uno
en la primera consulta y lo devuelve al cliente; en las siguientes, el cliente
lo reenvía y el servidor recupera el contador `turnos_sin_resultados` de esa
sesión. Cuando el contador alcanza `CHAT_UMBRAL_TURNOS_SIN_RESULTADOS`, el
pipeline responde `veredicto: escalar` con `razon: tope_turnos`.

La sesión vive **solo en memoria del proceso** (dict global) con TTL controlado
por `CHAT_TTL_SESION_SEG`; no se persiste en base y no expone el contador al
cliente. La purga es perezosa: al abrir u obtener una sesión se limpian las
expiradas, sin thread separado. Suficiente para un tenant chico single-worker;
un despliegue multi-worker o con reinicios frecuentes puede perder sesiones sin
consecuencias funcionales (solo se reinicia el contador; el chat sigue
funcionando).

El reloj es inyectable (`ahora`) para que los tests puedan simular la
expiración sin `time.sleep`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.config import get_settings


@dataclass
class SesionChat:
    """Sesión efímera del chat con su contador de resultados vacíos."""

    session_id: str
    creado_en: datetime
    ultimo_visto_en: datetime
    turnos_sin_resultados: int = 0


# Estado en memoria del proceso. Nunca se persiste y no se comparte entre
# workers. Un despliegue multi-worker puede llevar a que dos peticiones de la
# misma sesión caigan en workers distintos: en el peor caso, el contador arranca
# en 0 en el segundo worker (no hay corrupción, solo un "olvido").
_SESIONES: dict[str, SesionChat] = {}

# Reloj inyectable para tests. Devuelve `datetime` con tzinfo UTC.
_Ahora = Callable[[], datetime]
_ahora: _Ahora = lambda: datetime.now(timezone.utc)


def inyectar_reloj(ahora: _Ahora) -> None:
    """Reemplaza el reloj de las sesiones (solo para tests)."""
    global _ahora
    _ahora = ahora


def restaurar_reloj() -> None:
    """Restaura el reloj por defecto (tests)."""
    global _ahora
    _ahora = lambda: datetime.now(timezone.utc)


def reset_para_tests() -> None:
    """Limpia el diccionario de sesiones (solo para tests)."""
    _SESIONES.clear()


def _ttl_segundos() -> int:
    return get_settings().chat_ttl_sesion_seg


def _esta_expirada(sesion: SesionChat, ahora: datetime) -> bool:
    return (ahora - sesion.ultimo_visto_en).total_seconds() > _ttl_segundos()


def purgar_expiradas(ahora: datetime | None = None) -> None:
    """Elimina las sesiones cuyo TTL venció.

    Se llama de forma perezosa desde `abrir_sesion` y `obtener_sesion`; también
    la pueden invocar los tests para forzar una limpieza determinista.
    """
    if ahora is None:
        ahora = _ahora()
    expiradas = [sid for sid, s in _SESIONES.items() if _esta_expirada(s, ahora)]
    for sid in expiradas:
        _SESIONES.pop(sid, None)


def abrir_sesion() -> SesionChat:
    """Crea una sesión nueva con id opaco y contador a cero."""
    ahora = _ahora()
    purgar_expiradas(ahora)
    sesion = SesionChat(
        session_id=uuid.uuid4().hex,
        creado_en=ahora,
        ultimo_visto_en=ahora,
        turnos_sin_resultados=0,
    )
    _SESIONES[sesion.session_id] = sesion
    return sesion


def obtener_sesion(session_id: str | None) -> SesionChat | None:
    """Devuelve la sesión viva con ese id, o `None` si no existe o venció.

    Si venció, se limpia (y también las demás expiradas del diccionario).
    Actualiza `ultimo_visto_en` para renovar la ventana de TTL.
    """
    if not session_id:
        return None
    ahora = _ahora()
    sesion = _SESIONES.get(session_id)
    if sesion is None:
        purgar_expiradas(ahora)
        return None
    if _esta_expirada(sesion, ahora):
        # La purga elimina también las demás; luego se descarta esta.
        purgar_expiradas(ahora)
        _SESIONES.pop(session_id, None)
        return None
    sesion.ultimo_visto_en = ahora
    return sesion


def incrementar_sin_resultados(sesion: SesionChat) -> int:
    """Incrementa el contador de `sin_resultados` de la sesión y lo devuelve."""
    sesion.turnos_sin_resultados += 1
    sesion.ultimo_visto_en = _ahora()
    return sesion.turnos_sin_resultados


def resetear(sesion: SesionChat) -> None:
    """Pone a cero el contador (llamado tras `respondida`)."""
    sesion.turnos_sin_resultados = 0
    sesion.ultimo_visto_en = _ahora()
