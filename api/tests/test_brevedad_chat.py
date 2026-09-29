"""Tests de la política de brevedad del chat.

Cubre la garantía de la spec `chat-generativo-rag` de que una respuesta
`respondida` se recorta a `CHAT_LONGITUD_MAX_CHARS` cortando en el último
separador natural (`.` de frase o ` > ` de paso) y añadiendo `…`, sin cambiar
el veredicto ni las citas. También se prueban:

- que una respuesta corta pasa intacta;
- que la función pura `_recortar_suave` recorta por `.` y por ` > ` según cuál
  quede más tarde en la ventana;
- que el recorte NO se aplica a `sin_resultados` (mensaje canónico).
"""

from __future__ import annotations

import json

import pytest

from app import cache_chat as cache_mod
from app import chat as chat_mod
from app import sesiones_chat
from app.chat import _recortar_suave, responder
from app.config import get_settings
from app.recuperador import FragmentoRecuperado, ResultadoRecuperacion

PORTAL_A = "default"


class _ChatDoble:
    def __init__(self, respuestas: list[str]) -> None:
        self._respuestas = list(respuestas)
        self.llamadas: list[dict] = []

    def completar(
        self,
        messages: list[dict],
        *,
        response_format_json: bool,
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> str:
        self.llamadas.append(
            {
                "response_format_json": response_format_json,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if not self._respuestas:
            raise RuntimeError("Se llamó al chat más veces de las previstas por el test")
        return self._respuestas.pop(0)


@pytest.fixture(autouse=True)
def _reset_sesiones_y_factory():
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()
    yield
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()


def _fragmento() -> FragmentoRecuperado:
    return FragmentoRecuperado(
        tipo="articulo",
        portal_id=PORTAL_A,
        orden=0,
        texto="contenido de referencia del portal",
        similitud=0.9,
        origen={
            "articulo_id": "a1",
            "idioma": "es",
            "titulo": "Cómo hacer algo",
            "slug": "como-hacer-algo",
        },
    )


def _instalar_chat(monkeypatch, respuestas: list[str]) -> _ChatDoble:
    doble = _ChatDoble(respuestas)
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"),
    )
    return doble


# --- Función pura -----------------------------------------------------------


def test_recortar_suave_texto_corto_pasa_intacto():
    assert _recortar_suave("Hola.", 100) == "Hola."


def test_recortar_suave_corta_al_ultimo_punto_dentro_de_la_ventana():
    texto = (
        "Cambia tu contraseña desde ajustes. Ve a Cuenta y elige Seguridad. "
        "Introduce la nueva y confirma. Guarda los cambios."
    )
    recortado = _recortar_suave(texto, 80)
    # El corte cae en el último `.` que quepa; el sufijo `…` se añade.
    assert recortado.endswith("…")
    assert len(recortado) <= 80 + 1  # cabe el `…` extra
    assert recortado.count(".") >= 1
    # No se rompe una frase por la mitad: la frase incompleta queda fuera.
    assert "Introduce la nueva" not in recortado


def test_recortar_suave_prefiere_separador_de_paso_si_es_mas_tardio():
    texto = "Haz esto. paso 1 > paso 2 > paso 3 > paso 4 > paso 5"
    recortado = _recortar_suave(texto, 40)
    # El último " > " dentro de los 40 primeros caracteres gana al `.` previo.
    assert recortado.endswith(" > …")
    assert "paso 5" not in recortado


def test_recortar_suave_sin_separador_natural_hace_corte_duro():
    texto = "a" * 200
    recortado = _recortar_suave(texto, 50)
    assert recortado.endswith("…")
    assert len(recortado) <= 51


# --- Integración con el pipeline --------------------------------------------


def test_respuesta_larga_se_recorta_manteniendo_veredicto_respondida(
    db_session, monkeypatch,
):
    """Con `respondida` y una respuesta muy larga, el pipeline recorta con `…`
    sin degradar el veredicto ni descartar las citas."""
    maximo = get_settings().chat_longitud_max_chars
    respuesta_larga = ("Frase uno. " * 400).strip()  # muy por encima de 1400
    assert len(respuesta_larga) > maximo
    _instalar_chat(
        monkeypatch,
        respuestas=[
            "EN_SCOPE",
            json.dumps(
                {
                    "respuesta": respuesta_larga,
                    "citas_usadas": [1],
                    "encontrada": True,
                }
            ),
        ],
    )

    r = responder(
        consulta="¿cómo hago X?",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    assert r.veredicto == "respondida"
    assert len(r.mensaje) <= maximo + 1  # el `…` puede sumar un carácter
    assert r.mensaje.endswith("…")
    # Las citas se conservan intactas: el recorte solo toca el texto.
    assert [f.n for f in r.fuentes] == [1]


def test_respuesta_corta_pasa_intacta(db_session, monkeypatch):
    """Una respuesta corta y válida no se altera."""
    respuesta = "Se hace desde Ajustes > Seguridad."
    _instalar_chat(
        monkeypatch,
        respuestas=[
            "EN_SCOPE",
            json.dumps(
                {"respuesta": respuesta, "citas_usadas": [1], "encontrada": True}
            ),
        ],
    )

    r = responder(
        consulta="¿desde dónde?",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    assert r.veredicto == "respondida"
    assert r.mensaje == respuesta  # sin `…`, sin cambios


def test_recorte_no_se_aplica_a_sin_resultados(db_session, monkeypatch):
    """`sin_resultados` usa el mensaje canónico del pipeline, que puede ser
    breve; verificamos que la lógica de recorte solo actúa en `respondida` y
    no muta el texto de las plantillas."""
    doble = _ChatDoble(
        [
            "EN_SCOPE",
        ]
    )
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados"),
    )

    r = responder(
        consulta="pregunta sin match",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    assert r.veredicto == "sin_resultados"
    assert not r.mensaje.endswith("…")
