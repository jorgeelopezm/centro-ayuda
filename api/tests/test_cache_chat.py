"""Tests de la caché de respuesta del chat.

Cubre las tres garantías de la spec `chat-generativo-rag` (requisito
«Caché de respuesta por portal con revalidación de citas»):

- (a) La segunda consulta idéntica dentro del TTL se sirve del caché: solo
  se llama al clasificador de scope, no a la generación.
- (b) Borrar el artículo citado invalida la entrada y la siguiente consulta
  ejecuta el pipeline completo (revalidación por `slug`+portal).
- (c) `sin_resultados`, `escalar` y `fuera_de_scope` NO se cachean.

Además cubre la función pura `derivar_clave`: cambiar cualquiera de los
componentes cambia la clave (portal, idioma, config_ia, schema_recuperacion,
o consulta salvo por diferencias de espacio/caso).
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from app import cache_chat as cache_mod
from app import chat as chat_mod
from app import sesiones_chat
from app.cache_chat import derivar_clave, normalizar_consulta
from app.chat import responder
from app.models import Articulo, ArticuloTraduccion
from app.recuperador import FragmentoRecuperado, ResultadoRecuperacion
from app.servicios import PORTAL_DEFECTO_UUID

# `str(...)`: el pipeline del chat trata `portal_id` como texto de punta a
# punta; el portal `default` sembrado por `_sembrar_minimo` usa el UUID fijo
# `PORTAL_DEFECTO_UUID`.
PORTAL_A = str(PORTAL_DEFECTO_UUID)


class _ChatDoble:
    """Chat determinista: consume respuestas por llamada y cuenta invocaciones."""

    def __init__(self, respuestas: list[str]) -> None:
        self._respuestas = list(respuestas)
        self.llamadas: list[dict] = []

    def completar(
        self,
        messages,  # noqa: ANN001
        *,
        response_format_json: bool,
        temperature: float,
        max_tokens: int,
        timeout: float | None = None,
    ) -> str:
        self.llamadas.append({"response_format_json": response_format_json})
        if not self._respuestas:
            raise RuntimeError("Se llamó al chat más veces de las previstas")
        return self._respuestas.pop(0)


@pytest.fixture(autouse=True)
def _reset():
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()
    yield
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()


def _fragmento_articulo(slug: str = "como-hacer-algo") -> FragmentoRecuperado:
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
            "slug": slug,
        },
    )


def _sembrar_articulo(db, slug: str = "como-hacer-algo") -> None:
    """Siembra un artículo `a1` con su traducción `es` para que la revalidación
    del caché encuentre el `slug` en la base."""
    # `PORTAL_DEFECTO_UUID` (no `PORTAL_A`): estos son inserts ORM directos
    # contra columnas `Uuid`, que exigen el tipo Python nativo, no el `str`
    # que sí acepta el pipeline del chat en su frontera pública.
    db.add(
        Articulo(
            id="a1",
            portal_id=PORTAL_DEFECTO_UUID,
            categoria_id="cuenta",
            actualizado=date(2026, 8, 1),
            minutos_lectura=2,
            destacado=False,
            orden=0,
        )
    )
    db.add(
        ArticuloTraduccion(
            articulo_id="a1",
            portal_id=PORTAL_DEFECTO_UUID,
            idioma="es",
            slug=slug,
            titulo="Cómo hacer algo",
            parrafos=[],
            how_to={},
            faq=[],
        )
    )
    db.commit()


def _instalar_pipeline(monkeypatch, respuestas: list[str]) -> _ChatDoble:
    """Instala el chat doble y un recuperador que siempre devuelve el mismo
    fragmento del artículo sembrado (`slug=como-hacer-algo`)."""
    doble = _ChatDoble(respuestas)
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(
            fragmentos=[_fragmento_articulo()], veredicto="ok"
        ),
    )
    return doble


def _json_respondida(texto: str = "Ve a Ajustes > Seguridad.") -> str:
    return json.dumps(
        {"respuesta": texto, "citas_usadas": [1], "encontrada": True}
    )


# --- Función pura de clave ---------------------------------------------------


def test_normalizar_consulta_colapsa_espacios_y_baja_a_minusculas():
    assert normalizar_consulta("  ¿Cómo   cancelar? ") == "¿cómo cancelar?"


def test_derivar_clave_cambia_por_cada_componente():
    base = dict(
        portal_id="p1",
        idioma="es",
        consulta="hola",
        config_ia_version="v1",
        schema_recuperacion="r1",
    )
    k = derivar_clave(**base)
    # Cambiar cualquier componente cambia la clave.
    assert k != derivar_clave(**{**base, "portal_id": "p2"})
    assert k != derivar_clave(**{**base, "idioma": "pt"})
    assert k != derivar_clave(**{**base, "consulta": "adiós"})
    assert k != derivar_clave(**{**base, "config_ia_version": "v2"})
    assert k != derivar_clave(**{**base, "schema_recuperacion": "r2"})
    # Diferencias de espacio/caso NO cambian la clave (normalización).
    assert k == derivar_clave(**{**base, "consulta": "  HOLA "})


# --- Integración con el pipeline --------------------------------------------


def test_segundo_hit_se_sirve_del_cache(db_session, monkeypatch):
    """(a) Dos consultas idénticas del mismo portal dentro del TTL: la segunda
    NO invoca la generación. Solo hay una llamada extra al clasificador."""
    _sembrar_articulo(db_session)
    doble = _instalar_pipeline(
        monkeypatch,
        respuestas=["EN_SCOPE", _json_respondida(), "EN_SCOPE"],
    )

    r1 = responder(
        consulta="¿cómo hago X?",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )
    assert r1.veredicto == "respondida"
    # Primera vez: clasificador + generación.
    assert len(doble.llamadas) == 2

    r2 = responder(
        consulta="¿cómo hago X?",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )
    assert r2.veredicto == "respondida"
    assert r2.mensaje == r1.mensaje
    assert [f.slug for f in r2.fuentes] == [f.slug for f in r1.fuentes]
    # Segunda vez: solo clasificador; la generación se sirvió del caché.
    assert len(doble.llamadas) == 3
    # El chat_id cambia porque no reusamos `chat_id` entre requests (cada
    # request abre sesión nueva si no llega chat_id).
    # Lo importante es que el pipeline no volvió a llamar al proveedor de
    # generación.


def test_borrar_articulo_citado_invalida_la_entrada(db_session, monkeypatch):
    """(b) Tras un `respondida` cacheado, borrar el artículo citado hace que
    la siguiente consulta ejecute el pipeline completo (revalidación falla)."""
    _sembrar_articulo(db_session)
    doble = _instalar_pipeline(
        monkeypatch,
        respuestas=[
            "EN_SCOPE", _json_respondida("Primera."),
            "EN_SCOPE", _json_respondida("Segunda."),
        ],
    )

    r1 = responder(
        consulta="¿cómo hago X?",
        idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=None, solicitar_soporte=False, db=db_session,
    )
    assert r1.veredicto == "respondida"
    assert r1.mensaje == "Primera."

    # Borrar la traducción cuyo slug está en la entrada cacheada.
    db_session.query(ArticuloTraduccion).filter_by(
        articulo_id="a1", portal_id=PORTAL_DEFECTO_UUID
    ).delete()
    db_session.commit()

    r2 = responder(
        consulta="¿cómo hago X?",
        idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=None, solicitar_soporte=False, db=db_session,
    )
    assert r2.veredicto == "respondida"
    # No es el mensaje cacheado: se recomputó con la segunda respuesta del doble.
    assert r2.mensaje == "Segunda."
    # Se llamó al clasificador Y a la generación por segunda vez (4 llamadas).
    assert len(doble.llamadas) == 4


def test_sin_resultados_no_se_cachea(db_session, monkeypatch):
    """(c-sr) `sin_resultados` no entra al caché: la segunda consulta vuelve a
    llamar al clasificador Y al recuperador, no encuentra un hit servido."""
    doble = _ChatDoble(["EN_SCOPE", "EN_SCOPE"])
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(
            fragmentos=[], veredicto="sin_resultados"
        ),
    )

    r1 = responder(
        consulta="algo",
        idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=None, solicitar_soporte=False, db=db_session,
    )
    assert r1.veredicto == "sin_resultados"
    assert len(cache_mod.obtener_cache()) == 0

    r2 = responder(
        consulta="algo",
        idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=None, solicitar_soporte=False, db=db_session,
    )
    assert r2.veredicto == "sin_resultados"
    # Cada request llamó al clasificador (2 llamadas), y la caché sigue vacía.
    assert len(doble.llamadas) == 2
    assert len(cache_mod.obtener_cache()) == 0


def test_fuera_de_scope_no_se_cachea(db_session, monkeypatch):
    """(c-fs) `fuera_de_scope` no entra al caché."""
    doble = _ChatDoble(["FUERA_DE_SCOPE", "FUERA_DE_SCOPE"])
    chat_mod.inyectar_chat_factory(lambda _db: doble)
    # `recuperar` no debería llamarse ante fuera_de_scope, pero se stubbea por
    # si algún test futuro cruza el fixture.
    monkeypatch.setattr(
        chat_mod,
        "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(fragmentos=[], veredicto="ok"),
    )

    for _ in range(2):
        r = responder(
            consulta="¿qué opinas del clima?",
            idioma="es", historial=[], portal_id=PORTAL_A,
            chat_id=None, solicitar_soporte=False, db=db_session,
        )
        assert r.veredicto == "fuera_de_scope"

    # Se llamó al clasificador dos veces; caché sigue vacía.
    assert len(doble.llamadas) == 2
    assert len(cache_mod.obtener_cache()) == 0


def test_escalar_por_solicitud_no_se_cachea(db_session, monkeypatch):
    """(c-esc) Un `escalar` (por solicitud del usuario) no se cachea."""
    # Corto-circuito por `solicitar_soporte=True`: no llama al proveedor.
    r = responder(
        consulta="hola",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=True,
        db=db_session,
    )
    assert r.veredicto == "escalar"
    assert len(cache_mod.obtener_cache()) == 0
