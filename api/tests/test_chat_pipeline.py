"""Tests unitarios del pipeline `app.chat.responder`.

Cubre las garantías del pipeline sin salir a la red ni a un motor vectorial real:
- clasificador de scope: no llama al recuperador si está fuera; ante salida
  inesperada se asume `EN_SCOPE` (política conservadora) (7.5, 7.6).
- generación: prompt de sistema y datos van separados; JSON inválido, campo
  extra o cita fuera de rango → `sin_resultados` sin exponer la salida cruda;
  cita cuyo fragmento pertenece a otro portal → `sin_resultados` (7.7-7.9).
- escalamiento: `solicitar_soporte` corto-circuita; el segundo `sin_resultados`
  consecutivo escala; una `respondida` intermedia resetea el contador (7.10, 7.11).
- sesión efímera: TTL expirado emite `session_id` nuevo y resetea el contador;
  la purga perezosa no toca las sesiones vivas (7.12).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import cache_chat as cache_mod
from app import chat as chat_mod
from app import sesiones_chat
from app.chat import Turno, responder
from app.recuperador import FragmentoRecuperado, ResultadoRecuperacion

PORTAL_A = "default"
PORTAL_B = "otra-marca"


# --- Dobles del ProveedorChat -----------------------------------------------


class _ChatDoble:
    """Chat que devuelve respuestas prefabricadas por turno.

    Cada llamada consume la primera respuesta de `respuestas`; se registra la
    lista completa de mensajes recibidos en `llamadas` para inspeccionar la
    separación instrucción/dato en los tests.
    """

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
                "messages": list(messages),
                "response_format_json": response_format_json,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if not self._respuestas:
            raise RuntimeError("Se llamó al chat más veces de las previstas por el test")
        return self._respuestas.pop(0)


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_sesiones_y_factory():
    """Cada test arranca con el diccionario de sesiones vacío y el reloj real."""
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()
    yield
    sesiones_chat.reset_para_tests()
    sesiones_chat.restaurar_reloj()
    chat_mod.restaurar_chat_factory()
    cache_mod.reset_para_tests()


@pytest.fixture
def con_chat():
    """Instala un `_ChatDoble` como fábrica y lo devuelve para inspección."""
    def _instalar(respuestas: list[str]) -> _ChatDoble:
        doble = _ChatDoble(respuestas)
        chat_mod.inyectar_chat_factory(lambda _db: doble)
        return doble

    return _instalar


@pytest.fixture
def con_recuperador(monkeypatch):
    """Sustituye `app.chat.recuperar` para devolver un resultado prefabricado.

    Aísla el pipeline del recuperador real (ese ya se cubre en
    `test_chat_recuperador.py`).
    """
    def _instalar(resultado: ResultadoRecuperacion):
        monkeypatch.setattr(chat_mod, "recuperar", lambda *a, **kw: resultado)
        return resultado

    return _instalar


def _fragmento(
    *,
    tipo: str = "articulo",
    portal_id: str = PORTAL_A,
    texto: str = "contenido del portal",
    similitud: float = 0.9,
    articulo_id: str = "a1",
    idioma: str = "es",
    titulo: str = "Cómo hacer algo",
    slug: str = "como-hacer-algo",
    nombre: str = "manual.pdf",
    documento_id: int = 1,
) -> FragmentoRecuperado:
    if tipo == "articulo":
        origen = {
            "articulo_id": articulo_id,
            "idioma": idioma,
            "titulo": titulo,
            "slug": slug,
        }
    else:
        origen = {"documento_id": documento_id, "nombre": nombre}
    return FragmentoRecuperado(
        tipo=tipo,
        portal_id=portal_id,
        orden=0,
        texto=texto,
        similitud=similitud,
        origen=origen,
    )


def _ok(fragmentos: list[FragmentoRecuperado]) -> ResultadoRecuperacion:
    return ResultadoRecuperacion(fragmentos=fragmentos, veredicto="ok")


# --- 7.5 Clasificador fuera de scope ----------------------------------------


def test_fuera_de_scope_no_llama_al_recuperador_y_no_hay_conversacion(
    db_session, con_chat, monkeypatch,
):
    doble = con_chat(["FUERA_DE_SCOPE"])
    llamado = {"n": 0}
    def _no_llames(*a, **kw):  # pragma: no cover - falla si se llama
        llamado["n"] += 1
        raise AssertionError("El recuperador NO debe llamarse ante FUERA_DE_SCOPE")

    monkeypatch.setattr(chat_mod, "recuperar", _no_llames)

    r = responder(
        consulta="¿qué opinas del clima?",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    assert r.veredicto == "fuera_de_scope"
    assert r.conversacion == []
    assert r.fuentes == []
    assert r.razon is None
    # Solo se llamó una vez (al clasificador).
    assert len(doble.llamadas) == 1
    assert llamado["n"] == 0


# --- 7.6 Salida inesperada del clasificador → EN_SCOPE ----------------------


def test_clasificador_salida_inesperada_asume_en_scope(
    db_session, con_chat, con_recuperador,
):
    # Primera llamada = clasificador con salida rara; segunda = generación.
    doble = con_chat(
        [
            "quizás sí, quizás no",  # no contiene FUERA_DE_SCOPE
            '{"respuesta": "Se hace así.", "citas_usadas": [1], "encontrada": true}',
        ]
    )
    con_recuperador(_ok([_fragmento()]))

    r = responder(
        consulta="¿cómo cambio mi contraseña?",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    # Se procedió a recuperar y a generar: no se rechazó como fuera_de_scope.
    assert r.veredicto == "respondida"
    assert len(doble.llamadas) == 2


# --- 7.7 Generación: separación instrucción / dato --------------------------


def test_generacion_separa_prompt_de_sistema_de_los_datos(
    db_session, con_chat, con_recuperador,
):
    consulta = "TEXTO-CONSULTA-QUE-NO-DEBE-APARECER-EN-SYSTEM"
    fragmento_texto = "TEXTO-FRAGMENTO-QUE-NO-DEBE-APARECER-EN-SYSTEM"
    doble = con_chat(
        [
            "EN_SCOPE",
            '{"respuesta": "Sí.", "citas_usadas": [1], "encontrada": true}',
        ]
    )
    con_recuperador(_ok([_fragmento(texto=fragmento_texto)]))

    responder(
        consulta=consulta,
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    llamada_generacion = doble.llamadas[1]
    sistemas = [
        m["content"] for m in llamada_generacion["messages"] if m["role"] == "system"
    ]
    usuarios = [
        m["content"] for m in llamada_generacion["messages"] if m["role"] == "user"
    ]
    # El prompt de sistema NO lleva ni la consulta ni los fragmentos.
    for s in sistemas:
        assert consulta not in s
        assert fragmento_texto not in s
    # La consulta y el fragmento sí van en un mensaje de usuario, dentro del
    # delimitador `<contenido_no_confiable_<nonce>>`. El nonce cambia por
    # petición, así que el test comprueba el patrón base y que la etiqueta
    # abre y cierra dentro del mismo bloque.
    import re
    dato = "\n".join(usuarios)
    assert consulta in dato
    assert fragmento_texto in dato
    aperturas = re.findall(r"<contenido_no_confiable_[A-Za-z0-9_\-]+>", dato)
    cierres = re.findall(r"</contenido_no_confiable_[A-Za-z0-9_\-]+>", dato)
    assert aperturas, "Falta la etiqueta de apertura del delimitador con nonce"
    assert cierres, "Falta la etiqueta de cierre del delimitador con nonce"
    # Mismo nonce en apertura y cierre (misma petición).
    assert aperturas[0] == cierres[0].replace("/", "", 1)
    # Se pidió JSON estricto para la generación.
    assert llamada_generacion["response_format_json"] is True


# --- 7.8 Generación: JSON inválido, campo extra, cita fuera de rango --------


@pytest.mark.parametrize(
    "salida_bruta",
    [
        "esto no es JSON",  # JSON inválido
        '{"respuesta": "hola"}',  # falta `encontrada`
        '{"respuesta": "hola", "citas_usadas": [1], "encontrada": true, "extra": 1}',  # campo extra
        '{"respuesta": "hola", "citas_usadas": [99], "encontrada": true}',  # cita fantasma
        '{"respuesta": "hola", "citas_usadas": [0], "encontrada": true}',  # cita 0
        '{"respuesta": "", "citas_usadas": [1], "encontrada": true}',  # respuesta vacía
    ],
)
def test_generacion_salidas_invalidas_devuelven_sin_resultados_sin_exponer_crudo(
    db_session, con_chat, con_recuperador, salida_bruta,
):
    con_chat(["EN_SCOPE", salida_bruta])
    con_recuperador(_ok([_fragmento()]))

    r = responder(
        consulta="cualquier cosa",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    assert r.veredicto == "sin_resultados"
    # La salida bruta del proveedor NO viaja al cliente.
    assert salida_bruta not in r.mensaje
    assert r.fuentes == []


# --- 7.9 Cita cuyo fragmento pertenece a otro portal ------------------------


def test_cita_de_fragmento_de_otro_portal_devuelve_sin_resultados(
    db_session, con_chat, con_recuperador,
):
    # Fragmento del portal B en el resultado (situación forzada — el recuperador
    # real jamás lo devuelve; probamos la defensa en profundidad del pipeline).
    con_chat(
        [
            "EN_SCOPE",
            '{"respuesta": "Contenido cruzado.", "citas_usadas": [1], "encontrada": true}',
        ]
    )
    con_recuperador(_ok([_fragmento(portal_id=PORTAL_B)]))

    r = responder(
        consulta="cualquier cosa",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,  # host resuelto ≠ portal del fragmento
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )

    assert r.veredicto == "sin_resultados"
    assert r.fuentes == []


# --- 7.10 Corto-circuito por solicitar_soporte ------------------------------


def test_solicitar_soporte_true_corto_circuita_sin_llamar_al_proveedor(
    db_session, monkeypatch,
):
    # Si el pipeline llamara al chat o al recuperador, estos AssertionError
    # harían fallar el test.
    def _no_llames(*a, **kw):
        raise AssertionError("No debe invocarse")

    monkeypatch.setattr(chat_mod, "recuperar", _no_llames)

    class _ChatQueNoDebeSerLlamado:
        def completar(self, *a, **kw):
            raise AssertionError("No debe invocarse")

    chat_mod.inyectar_chat_factory(lambda _db: _ChatQueNoDebeSerLlamado())

    r = responder(
        consulta="necesito hablar con soporte",
        idioma="es",
        historial=[Turno(rol="asistente", texto="hola")],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=True,
        db=db_session,
    )

    assert r.veredicto == "escalar"
    assert r.razon == "solicitud_usuaria"
    # La conversación viaja para el correo de escalamiento (spec).
    roles = [t.rol for t in r.conversacion]
    assert roles == ["asistente", "usuario"]
    assert r.conversacion[-1].texto == "necesito hablar con soporte"


# --- 7.11 Escalamiento por tope de turnos y reseteo ------------------------


def test_segundo_sin_resultados_consecutivo_escala_por_tope(
    db_session, con_chat, con_recuperador,
):
    """Dos `sin_resultados` seguidos en la misma sesión → `escalar` (tope_turnos)."""
    # Ambos turnos: el clasificador dice EN_SCOPE y el recuperador no encuentra nada.
    con_chat(["EN_SCOPE", "EN_SCOPE"])
    con_recuperador(ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados"))

    r1 = responder(
        consulta="pregunta 1",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=None,
        solicitar_soporte=False,
        db=db_session,
    )
    assert r1.veredicto == "sin_resultados"

    r2 = responder(
        consulta="pregunta 2",
        idioma="es",
        historial=[],
        portal_id=PORTAL_A,
        chat_id=r1.chat_id,
        solicitar_soporte=False,
        db=db_session,
    )
    assert r2.veredicto == "escalar"
    assert r2.razon == "tope_turnos"
    # La conversación con la última pregunta viaja para escalamiento.
    assert r2.conversacion[-1].texto == "pregunta 2"


def test_respondida_intermedia_resetea_contador(
    db_session, monkeypatch, con_recuperador,
):
    """`sin_resultados` → `respondida` → `sin_resultados` NO debe escalar."""
    # Secuencia: clasif+clasif+gen+clasif; alternamos el resultado del recuperador.
    respuestas = [
        "EN_SCOPE",  # turno 1: clasificador
        "EN_SCOPE",  # turno 2: clasificador
        '{"respuesta": "Sí.", "citas_usadas": [1], "encontrada": true}',  # gen turno 2
        "EN_SCOPE",  # turno 3: clasificador
    ]
    doble = _ChatDoble(respuestas)
    chat_mod.inyectar_chat_factory(lambda _db: doble)

    resultados = [
        ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados"),
        ResultadoRecuperacion(fragmentos=[_fragmento()], veredicto="ok"),
        ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados"),
    ]
    it = iter(resultados)
    monkeypatch.setattr(chat_mod, "recuperar", lambda *a, **kw: next(it))

    r1 = responder(
        consulta="p1", idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=None, solicitar_soporte=False, db=db_session,
    )
    assert r1.veredicto == "sin_resultados"

    r2 = responder(
        consulta="p2", idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=r1.chat_id, solicitar_soporte=False, db=db_session,
    )
    assert r2.veredicto == "respondida"

    r3 = responder(
        consulta="p3", idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=r1.chat_id, solicitar_soporte=False, db=db_session,
    )
    # No escala: la `respondida` intermedia reseteó el contador.
    assert r3.veredicto == "sin_resultados"
    assert r3.razon is None


# --- 7.12 Sesión: TTL expirado + purga perezosa -----------------------------


def test_ttl_expirado_emite_session_id_nuevo_y_resetea_contador(
    db_session, con_chat, con_recuperador,
):
    """Cliente con `session_id` vencido → servidor lo ignora, emite uno nuevo y
    el contador arranca en 0 (no escala en la siguiente vuelta)."""
    reloj = {"t": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    sesiones_chat.inyectar_reloj(lambda: reloj["t"])

    # Turno 1: sin_resultados; contador = 1.
    con_chat(["EN_SCOPE", "EN_SCOPE"])
    con_recuperador(ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados"))

    r1 = responder(
        consulta="p1", idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=None, solicitar_soporte=False, db=db_session,
    )
    assert r1.veredicto == "sin_resultados"
    sid_viejo = r1.chat_id

    # Avanza el reloj MÁS ALLÁ del TTL.
    from app.config import get_settings
    reloj["t"] = reloj["t"] + timedelta(seconds=get_settings().chat_ttl_sesion_seg + 60)

    # Cliente sigue enviando el sid viejo: se ignora y se abre una sesión nueva.
    r2 = responder(
        consulta="p2", idioma="es", historial=[], portal_id=PORTAL_A,
        chat_id=sid_viejo, solicitar_soporte=False, db=db_session,
    )
    assert r2.veredicto == "sin_resultados"
    assert r2.chat_id != sid_viejo
    # No escaló: es el "primer" sin_resultados de la sesión nueva.
    assert r2.razon is None


def test_purga_perezosa_no_borra_sesiones_vivas():
    """`purgar_expiradas` no debe tocar sesiones cuyo TTL aún no venció."""
    reloj = {"t": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    sesiones_chat.inyectar_reloj(lambda: reloj["t"])

    viva = sesiones_chat.abrir_sesion()
    # Pequeño avance dentro del TTL (60 s << 1800 s).
    reloj["t"] = reloj["t"] + timedelta(seconds=60)
    sesiones_chat.purgar_expiradas()

    obtenida = sesiones_chat.obtener_sesion(viva.session_id)
    assert obtenida is not None
    assert obtenida.session_id == viva.session_id
