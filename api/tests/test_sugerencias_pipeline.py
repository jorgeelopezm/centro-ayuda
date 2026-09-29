"""Tests del pipeline de generación (`app.sugerencias.generar_borrador`, spec
`sugerencia-articulos-ia`).

Cubre la tarea 7.2: dobles de proveedor (chat + traducción) y del
recuperador, sin red, verificando JSON estricto, traducción bilingüe y el
cruce de citas contra fragmentos y portal.
"""

from __future__ import annotations

import logging
import re

import pytest

from app import sugerencias as sug_mod
from app.models import SugerenciaArticulo
from app.recuperador import FragmentoRecuperado, ResultadoRecuperacion
from app.servicios import PORTAL_DEFECTO_UUID
from app.servicios_ia import TIMEOUT_CHAT_SEG, TIMEOUT_GENERACION_SEG, ErrorProveedor
from app.sugerencias import Candidato, ErrorGeneracionSugerencia, generar_borrador

PORTAL_A = str(PORTAL_DEFECTO_UUID)
PORTAL_B = "00000000-0000-0000-0000-000000000099"


class _ChatDoble:
    def __init__(self, respuesta: str) -> None:
        self._respuesta = respuesta
        self.llamadas: list[dict] = []

    def completar(self, messages, *, response_format_json, temperature, max_tokens, timeout=None):
        self.llamadas.append(
            {
                "messages": list(messages),
                "response_format_json": response_format_json,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout,
            }
        )
        return self._respuesta


class _TraductorDoble:
    """Traductor determinista: antepone `PT:` a los textos, conserva la forma."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    def traducir(self, origen: str, destino: str, contenido: dict) -> dict:
        self.llamadas.append({"origen": origen, "destino": destino, "contenido": contenido})
        traducido = dict(contenido)
        traducido["titulo"] = f"PT:{contenido['titulo']}"
        traducido["parrafos"] = [f"PT:{p}" for p in contenido["parrafos"]]
        return traducido


@pytest.fixture(autouse=True)
def _reset_factories():
    sug_mod.restaurar_chat_factory()
    sug_mod.restaurar_traductor_factory()
    yield
    sug_mod.restaurar_chat_factory()
    sug_mod.restaurar_traductor_factory()


@pytest.fixture
def con_chat():
    def _instalar(respuesta: str) -> _ChatDoble:
        doble = _ChatDoble(respuesta)
        sug_mod.inyectar_chat_factory(lambda _db: doble)
        return doble

    return _instalar


@pytest.fixture
def con_traductor():
    def _instalar() -> _TraductorDoble:
        doble = _TraductorDoble()
        sug_mod.inyectar_traductor_factory(lambda _db: doble)
        return doble

    return _instalar


@pytest.fixture
def con_recuperador(monkeypatch):
    def _instalar(resultado: ResultadoRecuperacion):
        monkeypatch.setattr(sug_mod, "recuperar", lambda *a, **kw: resultado)
        return resultado

    return _instalar


def _fragmento(*, portal_id: str = PORTAL_A, texto: str = "fragmento del portal", tipo: str = "articulo") -> FragmentoRecuperado:
    origen = (
        {"articulo_id": "a1", "idioma": "es", "titulo": "Artículo A", "slug": "articulo-a"}
        if tipo == "articulo"
        else {"documento_id": 1, "nombre": "manual.pdf"}
    )
    return FragmentoRecuperado(tipo=tipo, portal_id=portal_id, orden=0, texto=texto, similitud=0.9, origen=origen)


def _candidato(titulo: str = "cómo cancelo mi cuenta") -> Candidato:
    return Candidato(
        fuente="chat_escalado",
        referencia="consulta:abc123",
        titulo_sugerido=titulo,
        idioma="es",
        prioridad=1,
    )


_JSON_VALIDO = (
    '{"titulo": "Cómo cancelar tu cuenta", '
    '"parrafos": ["Sigue estos pasos."], '
    '"howTo": {"titulo": "Pasos", "pasos": [{"titulo": "Entra a ajustes", "descripcion": "Ve a Ajustes."}]}, '
    '"nota": null, '
    '"faq": [{"pregunta": "¿Se puede deshacer?", "respuesta": "No."}], '
    '"citas_usadas": [1]}'
)


# --- Generación feliz ---------------------------------------------------------


def test_genera_borrador_bilingue_y_persiste_pendiente(db_session, con_chat, con_traductor, con_recuperador):
    con_chat(_JSON_VALIDO)
    traductor = con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"))

    sugerencia = generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert sugerencia.estado == "pendiente"
    assert sugerencia.articulo_id is None
    assert sugerencia.fuente == "chat_escalado"
    assert sugerencia.contenido["es"]["titulo"] == "Cómo cancelar tu cuenta"
    assert sugerencia.contenido["pt"]["titulo"] == "PT:Cómo cancelar tu cuenta"
    assert sugerencia.contenido["es"]["slug"] == sugerencia.contenido["pt"]["slug"]
    assert len(sugerencia.citas) == 1
    assert sugerencia.citas[0]["tipo"] == "articulo"
    assert traductor.llamadas[0]["origen"] == "es"

    # Se persistió realmente (no solo el objeto en memoria).
    en_db = db_session.get(SugerenciaArticulo, sugerencia.id)
    assert en_db is not None
    assert en_db.estado == "pendiente"


def test_generacion_separa_prompt_de_sistema_de_los_datos(db_session, con_chat, con_traductor, con_recuperador):
    señal = "SEÑAL-QUE-NO-DEBE-APARECER-EN-SYSTEM"
    fragmento_texto = "FRAGMENTO-QUE-NO-DEBE-APARECER-EN-SYSTEM"
    doble = con_chat(_JSON_VALIDO)
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento(texto=fragmento_texto)], veredicto="ok"))

    generar_borrador(_candidato(señal), PORTAL_A, "editor@test.local", db_session)

    llamada = doble.llamadas[0]
    sistemas = [m["content"] for m in llamada["messages"] if m["role"] == "system"]
    usuarios = [m["content"] for m in llamada["messages"] if m["role"] == "user"]
    for s in sistemas:
        assert señal not in s
        assert fragmento_texto not in s
    dato = "\n".join(usuarios)
    assert señal in dato
    assert fragmento_texto in dato
    aperturas = re.findall(r"<contenido_no_confiable_[A-Za-z0-9_\-]+>", dato)
    cierres = re.findall(r"</contenido_no_confiable_[A-Za-z0-9_\-]+>", dato)
    assert aperturas and cierres
    assert aperturas[0] == cierres[0].replace("/", "", 1)
    assert llamada["response_format_json"] is True


# --- Salidas inválidas del LLM ------------------------------------------------


@pytest.mark.parametrize(
    "salida_bruta",
    [
        "esto no es JSON",
        '{"titulo": "x"}',  # faltan campos obligatorios
        '{"titulo": "x", "parrafos": [], "howTo": {"titulo": "p", "pasos": []}, '
        '"nota": null, "faq": [], "citas_usadas": [], "extra": 1}',  # campo extra
    ],
)
def test_salida_invalida_levanta_error_sin_persistir(
    db_session, con_chat, con_traductor, con_recuperador, salida_bruta,
):
    con_chat(salida_bruta)
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"))

    with pytest.raises(ErrorGeneracionSugerencia):
        generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert db_session.query(SugerenciaArticulo).count() == 0


# --- Citas ---------------------------------------------------------------


def test_cita_fuera_de_rango_se_descarta_pero_la_sugerencia_se_genera(
    db_session, con_chat, con_traductor, con_recuperador,
):
    salida = _JSON_VALIDO.replace('"citas_usadas": [1]', '"citas_usadas": [99]')
    con_chat(salida)
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"))

    sugerencia = generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert sugerencia.estado == "pendiente"
    assert sugerencia.citas == []


def test_cita_de_fragmento_de_otro_portal_se_descarta(db_session, con_chat, con_traductor, con_recuperador):
    con_chat(_JSON_VALIDO)
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento(portal_id=PORTAL_B)], veredicto="ok"))

    sugerencia = generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert sugerencia.citas == []


def test_sin_fragmentos_recuperados_igual_genera_borrador(db_session, con_chat, con_traductor, con_recuperador):
    salida = _JSON_VALIDO.replace('"citas_usadas": [1]', '"citas_usadas": []')
    con_chat(salida)
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados"))

    sugerencia = generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert sugerencia.estado == "pendiente"
    assert sugerencia.citas == []


# --- Slug de emergencia --------------------------------------------------


def test_titulo_sin_alfanumericos_cae_a_slug_de_emergencia(
    db_session, con_chat, con_traductor, con_recuperador,
):
    salida = _JSON_VALIDO.replace('"titulo": "Cómo cancelar tu cuenta"', '"titulo": "???"')
    con_chat(salida)
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"))

    sugerencia = generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert sugerencia.contenido["es"]["slug"] == "borrador-sugerido"


# --- Timeout y atribución de etapa -------------------------------------------
#
# Regresión del 502 en «Generar borrador con IA»: la generación reutilizaba el
# cliente del chat con su timeout de 30 s (dimensionado para 512 tokens) pese a
# pedir `MAX_TOKENS_SUGERENCIA` = 2048, así que moría por timeout de forma
# sistemática y salía como un 502 indistinguible de un bug propio.


def test_la_generacion_pide_timeout_holgado_no_el_del_chat(
    db_session, con_chat, con_traductor, con_recuperador
):
    """El techo de tokens y el timeout tienen que ir de la mano: pedir 2048 tokens
    con el presupuesto de 30 s del chat es lo que provocaba el 502."""
    doble = con_chat(_JSON_VALIDO)
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"))

    generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    llamada = doble.llamadas[0]
    assert llamada["max_tokens"] == sug_mod.MAX_TOKENS_SUGERENCIA
    assert llamada["timeout"] == TIMEOUT_GENERACION_SEG
    assert llamada["timeout"] > TIMEOUT_CHAT_SEG


def test_fallo_del_proveedor_al_redactar_identifica_la_etapa(
    db_session, con_chat, con_traductor, con_recuperador, caplog
):
    """Redacción y traducción levantan el MISMO `ErrorProveedor` y dan el mismo
    502, así que sin la etapa en el log no se sabe cuál de las dos falló."""
    class _ChatQueFalla:
        def completar(self, *a, **kw):
            raise ErrorProveedor("402 Insufficient Balance")

    sug_mod.inyectar_chat_factory(lambda _db: _ChatQueFalla())
    con_traductor()
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"))

    with caplog.at_level(logging.WARNING, logger="app.sugerencias"):
        with pytest.raises(ErrorProveedor):
            generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert "etapa=redaccion" in caplog.text
    # El mensaje real del proveedor tiene que sobrevivir hasta el log: es la única
    # copia (el manejador de `app.main` responde un texto genérico al cliente).
    assert "402 Insufficient Balance" in caplog.text


def test_fallo_del_proveedor_al_traducir_identifica_la_etapa(
    db_session, con_chat, con_recuperador, caplog
):
    con_chat(_JSON_VALIDO)
    con_recuperador(ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"))

    class _TraductorQueFalla:
        def traducir(self, origen, destino, contenido):
            raise ErrorProveedor("La traducción cambió las claves de howTo.")

    sug_mod.inyectar_traductor_factory(lambda _db: _TraductorQueFalla())

    with caplog.at_level(logging.WARNING, logger="app.sugerencias"):
        with pytest.raises(ErrorProveedor):
            generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert "etapa=traduccion" in caplog.text
    # Nada se persiste si la mitad portuguesa falla: el artículo es bilingüe atómico.
    assert db_session.query(SugerenciaArticulo).count() == 0


def test_recuperacion_fallida_deja_rastro_en_el_log(
    db_session, con_chat, con_traductor, con_recuperador, caplog
):
    """Un embebedor caído degradaba a «redactar sin contexto» en silencio, y el
    borrador degenerado resultante moría luego como un 502 sin pista de la causa."""
    con_chat(_JSON_VALIDO)
    con_traductor()
    con_recuperador(
        ResultadoRecuperacion(fragmentos=[], veredicto="error_proveedor", detalle="embedder")
    )

    with caplog.at_level(logging.WARNING, logger="app.sugerencias"):
        generar_borrador(_candidato(), PORTAL_A, "editor@test.local", db_session)

    assert "veredicto=error_proveedor" in caplog.text
    assert "sin contexto" in caplog.text
