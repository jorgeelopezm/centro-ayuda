"""Tests de los endpoints de sugerencias (`api/app/routers/admin_sugerencias.py`,
spec `sugerencia-articulos-ia`).

Cubre las tareas 7.3 (autorización, aislamiento por portal, idempotencia,
aceptar/descartar) y 7.4 (una sugerencia `pendiente` no es visible en el
centro público).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import ingesta
from app import sugerencias as sug_mod
from app.database import get_db
from app.main import app
from app.models import PreguntaSinResolver, SugerenciaArticulo
from app.recuperador import ResultadoRecuperacion
from app.servicios import PORTAL_DEFECTO_UUID
from tests.conftest import (
    ADMIN_EMAIL,
    EDITOR_EMAIL,
    EDITOR_PASSWORD,
    SEGUNDO_ADMIN_PASSWORD,
    SEGUNDO_PORTAL_HOST,
    SEGUNDO_PORTAL_UUID,
    articulo_valido,
    sembrar_portal_secundario,
)

PORTAL_A = PORTAL_DEFECTO_UUID

_JSON_VALIDO = (
    '{"titulo": "Cómo cancelar tu cuenta", '
    '"parrafos": ["Sigue estos pasos."], '
    '"howTo": {"titulo": "Pasos", "pasos": [{"titulo": "Entra a ajustes", "descripcion": "Ve a Ajustes."}]}, '
    '"nota": null, '
    '"faq": [{"pregunta": "¿Se puede deshacer?", "respuesta": "No."}], '
    '"citas_usadas": []}'
)


class _ChatDoble:
    def __init__(self, respuesta: str = _JSON_VALIDO) -> None:
        self._respuesta = respuesta
        self.llamadas = 0

    def completar(self, messages, *, response_format_json, temperature, max_tokens, timeout=None):
        self.llamadas += 1
        return self._respuesta


class _TraductorDoble:
    def traducir(self, origen, destino, contenido):
        traducido = dict(contenido)
        traducido["titulo"] = f"PT:{contenido['titulo']}"
        return traducido


@pytest.fixture(autouse=True)
def _reset_factories():
    sug_mod.restaurar_chat_factory()
    sug_mod.restaurar_traductor_factory()
    yield
    sug_mod.restaurar_chat_factory()
    sug_mod.restaurar_traductor_factory()


@pytest.fixture
def hacer_cliente(db_session):
    """Fábrica de clientes por host que comparten la misma sesión de base
    (espeja `hacer_cliente` de `test_admin_chats.py`)."""
    sembrar_portal_secundario(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield lambda host: TestClient(app, base_url=f"http://{host}")
    app.dependency_overrides.clear()


@pytest.fixture
def con_ia(db_session, monkeypatch):
    """Instala dobles deterministas de chat/traducción y un recuperador sin
    fragmentos (no hace falta un embedder real: `sugerencias.recuperar` se
    sustituye directamente, como en `test_sugerencias_pipeline.py`)."""
    chat = _ChatDoble()
    sug_mod.inyectar_chat_factory(lambda _db: chat)
    sug_mod.inyectar_traductor_factory(lambda _db: _TraductorDoble())
    monkeypatch.setattr(
        sug_mod, "recuperar",
        lambda *a, **kw: ResultadoRecuperacion(fragmentos=[], veredicto="sin_resultados"),
    )
    return chat


@pytest.fixture
def con_reindexado(db_session):
    """Bindea el background de re-indexado (`ingesta.reindexar_articulo`) al
    SQLite en memoria de la prueba, con un embedder determinista (patrón de
    `test_admin_documentos.con_embedder_bueno`)."""
    ingesta.inyectar_embedder_factory(lambda _db: _EmbedderDoble())
    engine = db_session.get_bind()
    ingesta.inyectar_sesion_factory(sessionmaker(bind=engine, autoflush=False, autocommit=False))
    yield
    ingesta.restaurar_embedder_factory()
    ingesta.restaurar_sesion_factory()


class _EmbedderDoble:
    def embeber(self, textos):
        return [[float(len(t))] for t in textos]


def _auth(cliente: TestClient, email: str, password: str) -> dict:
    r = cliente.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sembrar_pregunta(db, *, portal_id, pregunta: str = "¿Cómo exporto mis datos?") -> PreguntaSinResolver:
    p = PreguntaSinResolver(
        portal_id=portal_id, idioma="es", pregunta=pregunta, veces=4,
        similitud=0.4, fecha=date(2026, 8, 1), estado="nueva", orden=5,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# --- (a) Anonymous -> 401 en todos los endpoints -----------------------------


def test_anonymous_no_puede_acceder_a_ningun_endpoint(hacer_cliente):
    a = hacer_cliente("localhost")

    assert a.get("/api/admin/sugerencias/candidatos").status_code == 401
    assert a.post("/api/admin/sugerencias/generar", json={"fuente": "chat_escalado", "referencia": "x"}).status_code == 401
    assert a.get("/api/admin/sugerencias").status_code == 401
    assert a.get("/api/admin/sugerencias/algun-id").status_code == 401
    assert a.post("/api/admin/sugerencias/algun-id/aceptar", json=articulo_valido()).status_code == 401
    assert a.post("/api/admin/sugerencias/algun-id/descartar").status_code == 401


# --- Candidatos ---------------------------------------------------------------


def test_editor_ve_candidatos_de_su_portal_no_del_otro(hacer_cliente, db_session):
    _sembrar_pregunta(db_session, portal_id=PORTAL_A, pregunta="pregunta del portal A")
    _sembrar_pregunta(db_session, portal_id=SEGUNDO_PORTAL_UUID, pregunta="pregunta del portal B")

    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.get("/api/admin/sugerencias/candidatos?fuente=pregunta_sin_resolver", headers=auth)
    assert r.status_code == 200, r.text
    titulos = {it["titulo_sugerido"] for it in r.json()["items"]}
    assert "pregunta del portal A" in titulos
    assert "pregunta del portal B" not in titulos


# --- Generar (idempotencia + 404) --------------------------------------------


def test_generar_crea_borrador_pendiente(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "pendiente"
    assert cuerpo["es"]["titulo"] == "Cómo cancelar tu cuenta"
    assert cuerpo["pt"]["titulo"] == "PT:Cómo cancelar tu cuenta"
    assert cuerpo["portal_id"] == str(PORTAL_A)


def test_generar_es_idempotente_para_el_mismo_candidato_pendiente(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    body = {"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"}

    r1 = a.post("/api/admin/sugerencias/generar", json=body, headers=auth)
    r2 = a.post("/api/admin/sugerencias/generar", json=body, headers=auth)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    # El proveedor de chat solo se invocó una vez: la segunda llamada devolvió
    # la sugerencia `pendiente` existente sin regenerar.
    assert con_ia.llamadas == 1


def test_generar_candidato_inexistente_es_404(hacer_cliente, con_ia):
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": "pregunta:9999"},
        headers=auth,
    )
    assert r.status_code == 404


# --- Detalle / listado: aislamiento por portal --------------------------------


def test_detalle_de_sugerencia_de_otro_portal_es_404(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth_a = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    creada = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth_a,
    ).json()

    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_b = _auth(b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)

    r = b.get(f"/api/admin/sugerencias/{creada['id']}", headers=auth_b)
    assert r.status_code == 404


def test_listar_solo_devuelve_pendientes_del_portal(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    )

    r = a.get("/api/admin/sugerencias", headers=auth)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["estado"] == "pendiente"


# --- Aceptar -------------------------------------------------------------


def test_aceptar_crea_articulo_y_reindexa(hacer_cliente, db_session, con_ia, con_reindexado):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    creada = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    ).json()

    payload = articulo_valido("cancelar-cuenta")
    r = a.post(f"/api/admin/sugerencias/{creada['id']}/aceptar", json=payload, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "cancelar-cuenta"

    # El artículo real existe ahora.
    assert a.get("/api/admin/articulos/cancelar-cuenta", headers=auth).status_code == 200

    # La sugerencia queda `aceptada`, referenciando el artículo creado.
    sugerencia = db_session.get(SugerenciaArticulo, uuid.UUID(creada["id"]))
    assert sugerencia.estado == "aceptada"
    assert sugerencia.articulo_id == "cancelar-cuenta"
    assert sugerencia.resuelto_en is not None

    # El re-indexado en background corrió: hay fragmentos del artículo.
    from app.models import ArticuloChunk

    assert db_session.query(ArticuloChunk).filter(ArticuloChunk.articulo_id == "cancelar-cuenta").count() > 0


def test_aceptar_incompleto_no_publica_y_deja_pendiente(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    creada = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    ).json()

    payload = articulo_valido("incompleto")
    del payload["pt"]
    r = a.post(f"/api/admin/sugerencias/{creada['id']}/aceptar", json=payload, headers=auth)
    assert r.status_code == 422

    sugerencia = db_session.get(SugerenciaArticulo, uuid.UUID(creada["id"]))
    assert sugerencia.estado == "pendiente"
    assert a.get("/api/admin/articulos/incompleto", headers=auth).status_code == 404


def test_aceptar_sugerencia_ya_resuelta_es_409(hacer_cliente, db_session, con_ia, con_reindexado):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    creada = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    ).json()

    a.post(
        f"/api/admin/sugerencias/{creada['id']}/aceptar",
        json=articulo_valido("cancelar-cuenta"),
        headers=auth,
    )
    r = a.post(
        f"/api/admin/sugerencias/{creada['id']}/aceptar",
        json=articulo_valido("otro-intento"),
        headers=auth,
    )
    assert r.status_code == 409


# --- Descartar -----------------------------------------------------------


def test_descartar_no_publica_nada(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    creada = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    ).json()

    r = a.post(f"/api/admin/sugerencias/{creada['id']}/descartar", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "descartada"

    sugerencia = db_session.get(SugerenciaArticulo, uuid.UUID(creada["id"]))
    assert sugerencia.estado == "descartada"
    assert sugerencia.articulo_id is None

    # No aparece más en la cola de pendientes.
    assert a.get("/api/admin/sugerencias", headers=auth).json()["items"] == []


def test_descartar_sugerencia_ya_resuelta_es_409(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    creada = a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    ).json()

    a.post(f"/api/admin/sugerencias/{creada['id']}/descartar", headers=auth)
    r = a.post(f"/api/admin/sugerencias/{creada['id']}/descartar", headers=auth)
    assert r.status_code == 409


# --- (7.4) Una sugerencia `pendiente` no es pública ni se indexa -------------


def test_sugerencia_pendiente_no_aparece_en_el_contenido_publico(hacer_cliente, db_session, con_ia):
    p = _sembrar_pregunta(db_session, portal_id=PORTAL_A)
    a = hacer_cliente("localhost")
    auth = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)
    a.post(
        "/api/admin/sugerencias/generar",
        json={"fuente": "pregunta_sin_resolver", "referencia": f"pregunta:{p.id}"},
        headers=auth,
    )

    publico = a.get("/api/es/contenido").json()
    titulos = {art["titulo"] for art in publico["articulos"]}
    assert "Cómo cancelar tu cuenta" not in titulos

    # Tampoco tiene fragmentos indexados para el RAG: nunca se creó un `Articulo`.
    from app.models import ArticuloChunk

    assert db_session.query(ArticuloChunk).count() == 0
