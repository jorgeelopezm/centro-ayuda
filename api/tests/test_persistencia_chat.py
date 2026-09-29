"""Tests de persistencia de interacciones de chat en `chat_interaccion`.

Cubre los tres invariantes del requisito `Persistencia por interacción` de
`supervision-chats`:

- (a) Se persiste UNA fila por invocación de `responder`, con los datos del
  turno (portal, chat_id, veredicto, mensaje, citas, proveedor, modelo,
  latencia).
- (b) Un segundo turno del MISMO `chat_id` recibe `turno=2`.
- (c) Si el `INSERT` lanza excepción, la respuesta al usuario sigue
  devolviéndose (garantía "un fallo al persistir no rompe la respuesta").

Usa dobles del proveedor de chat y del recuperador (mismo patrón que
`test_chat_pipeline.py`), sin salir a la red ni requerir Postgres.
"""

from __future__ import annotations

import pytest

from app import cache_chat as cache_mod
from app import chat as chat_mod
from app import persistencia_chat, sesiones_chat
from app.chat import responder
from app.models import ChatInteraccion
from app.recuperador import FragmentoRecuperado, ResultadoRecuperacion
from app.servicios import PORTAL_DEFECTO_UUID

# `str(...)`: el pipeline del chat trata `portal_id` como texto de punta a
# punta (lo resuelve así el router); el portal `default` sembrado por
# `_sembrar_minimo` usa el UUID fijo `PORTAL_DEFECTO_UUID`.
PORTAL_A = str(PORTAL_DEFECTO_UUID)


class _ChatDoble:
    """Chat determinista: consume respuestas prefabricadas por llamada."""

    def __init__(self, respuestas: list[str]) -> None:
        self._respuestas = list(respuestas)

    def completar(self, messages, *, response_format_json, temperature, max_tokens, timeout=None):  # noqa: ANN001
        if not self._respuestas:
            raise RuntimeError("Se llamó al chat más veces de las previstas por el test")
        return self._respuestas.pop(0)


def _fragmento() -> FragmentoRecuperado:
    return FragmentoRecuperado(
        tipo="articulo",
        portal_id=PORTAL_A,
        orden=0,
        texto="contenido",
        similitud=0.9,
        origen={
            "articulo_id": "a1",
            "idioma": "es",
            "titulo": "Cómo hacer algo",
            "slug": "como-hacer-algo",
        },
    )


@pytest.fixture(autouse=True)
def _reset_estado_chat():
    """Cada test arranca con sesiones y fábrica de chat limpias."""
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()
    yield
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()


def test_una_respuesta_persiste_una_fila_con_metadatos(
    db_session, monkeypatch,
):
    """(a) Tras `responder` con veredicto `respondida`, hay UNA fila en
    `chat_interaccion` con los datos del turno."""
    doble = _ChatDoble(
        [
            "EN_SCOPE",
            '{"respuesta": "Se hace [1].", "citas_usadas": [1], "encontrada": true}',
        ]
    )
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"),
    )

    resp = responder(
        consulta="cómo hago X",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )
    assert resp.veredicto == "respondida"

    filas = db_session.query(ChatInteraccion).all()
    assert len(filas) == 1
    fila = filas[0]
    assert str(fila.portal_id) == PORTAL_A
    assert fila.chat_id == resp.chat_id
    assert fila.turno == 1
    assert fila.idioma == "es"
    assert fila.consulta == "cómo hago X"
    assert fila.veredicto == "respondida"
    assert fila.mensaje == "Se hace [1]."
    assert fila.citas == [
        {"n": 1, "tipo": "articulo", "titulo": "Cómo hacer algo", "slug": "como-hacer-algo"}
    ]
    assert fila.razon_escalamiento is None
    assert fila.latencia_ms >= 0
    # `proveedor` y `modelo` salen de defaults al no haber `ConfigIA` en el seed mínimo.
    assert fila.proveedor == "deepseek"
    assert fila.modelo == "deepseek-chat"


def test_segundo_turno_del_mismo_chat_id_recibe_turno_2(
    db_session, monkeypatch,
):
    """(b) Dos consultas seguidas con el mismo `chat_id` producen `turno=1` y
    `turno=2` en `chat_interaccion`."""
    doble = _ChatDoble(
        [
            "EN_SCOPE",
            '{"respuesta": "Uno [1].", "citas_usadas": [1], "encontrada": true}',
            "EN_SCOPE",
            '{"respuesta": "Dos [1].", "citas_usadas": [1], "encontrada": true}',
        ]
    )
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"),
    )

    r1 = responder(
        consulta="q1", idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=None, solicitar_soporte=False, db=db_session,
    )
    r2 = responder(
        consulta="q2", idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=r1.chat_id, solicitar_soporte=False, db=db_session,
    )

    assert r1.chat_id == r2.chat_id
    filas = (
        db_session.query(ChatInteraccion)
        .filter(ChatInteraccion.chat_id == r1.chat_id)
        .order_by(ChatInteraccion.turno)
        .all()
    )
    assert [f.turno for f in filas] == [1, 2]
    assert [f.consulta for f in filas] == ["q1", "q2"]


def test_fallo_al_persistir_no_rompe_la_respuesta(
    db_session, monkeypatch,
):
    """(c) Si `persistir` lanza (INSERT rechazado, base indisponible, ...), el
    usuario recibe igual la respuesta del pipeline."""
    doble = _ChatDoble(
        [
            "EN_SCOPE",
            '{"respuesta": "Se hace [1].", "citas_usadas": [1], "encontrada": true}',
        ]
    )
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"),
    )

    # Forzamos que `persistir` explote. `persistencia_chat.persistir` captura
    # cualquier excepción y solo loguea, así que el pipeline sigue devolviendo
    # la respuesta al usuario intacta.
    def _explota(*_a, **_kw):
        raise RuntimeError("base indisponible")

    monkeypatch.setattr(persistencia_chat, "persistir", _explota)
    monkeypatch.setattr(chat_mod, "persistir", _explota)

    resp = responder(
        consulta="cómo hago X",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    # La respuesta se emite igual; en la base no queda fila (el "persistir"
    # inyectado no la escribe).
    assert resp.veredicto == "respondida"
    assert resp.mensaje == "Se hace [1]."
    assert db_session.query(ChatInteraccion).count() == 0
