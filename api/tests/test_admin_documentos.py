"""Endpoints de gestión de documentos del índice RAG.

Cubre validación de formato/tamaño, transiciones de estado
(`pendiente|procesando|listo|error`), autorización por nivel y aislamiento por
portal. El proveedor de embeddings se sustituye por un doble determinista para
no depender de red ni de una clave real; la fábrica de sesión también se
inyecta para que el background use el SQLite en memoria de la prueba.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import ingesta
from app.database import get_db
from app.main import app
from app.models import ArticuloChunk, Documento, DocumentoChunk
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    SEGUNDO_ADMIN_PASSWORD,
    SEGUNDO_PORTAL_HOST,
    SEGUNDO_PORTAL_UUID,
    articulo_valido,
    sembrar_portal_secundario,
)


class _EmbedderDoble:
    """Embedder determinista: un vector `[len(texto)]` por texto de entrada."""

    def __init__(self) -> None:
        self.llamadas: list[list[str]] = []

    def embeber(self, textos: list[str]) -> list[list[float]]:
        self.llamadas.append(list(textos))
        return [[float(len(t))] for t in textos]


class _EmbedderQueFalla:
    """Embedder que siempre falla: para verificar la transición a `error`."""

    def embeber(self, textos: list[str]) -> list[list[float]]:
        raise RuntimeError("Proveedor no disponible")


@pytest.fixture
def con_embedder_bueno(db_session):
    """Inyecta un embedder determinista y bindea el background al SQLite de test."""
    doble = _EmbedderDoble()
    ingesta.inyectar_embedder_factory(lambda _db: doble)

    # Devuelve una sesión NUEVA sobre el mismo engine del test, para que el
    # background no reuse la misma `Session` que la petición.
    engine = db_session.get_bind()
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ingesta.inyectar_sesion_factory(factory)
    yield doble
    ingesta.restaurar_embedder_factory()
    ingesta.restaurar_sesion_factory()


@pytest.fixture
def con_embedder_que_falla(db_session):
    """Como `con_embedder_bueno` pero el proveedor de embeddings siempre falla."""
    ingesta.inyectar_embedder_factory(lambda _db: _EmbedderQueFalla())
    engine = db_session.get_bind()
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    ingesta.inyectar_sesion_factory(factory)
    yield
    ingesta.restaurar_embedder_factory()
    ingesta.restaurar_sesion_factory()


def _subir_txt(client, auth: dict, texto: str = "hola mundo", nombre: str = "doc.txt"):
    return client.post(
        "/api/admin/documentos",
        content=texto.encode("utf-8"),
        headers={
            **auth,
            "Content-Type": "text/plain",
            "Content-Disposition": f'attachment; filename="{nombre}"',
        },
    )


# --- Validación de la subida -----------------------------------------------


def test_subida_valida_pasa_a_listo(client, auth, con_embedder_bueno, db_session):
    r = _subir_txt(client, auth, texto="Un párrafo.\n\nOtro párrafo.")
    assert r.status_code == 201, r.text
    salida = r.json()
    assert salida["nombre"] == "doc.txt"
    assert salida["mime"] == "text/plain"

    # BackgroundTasks del TestClient corren de forma síncrona: al volver de la
    # petición ya se ejecutó la ingesta.
    db_session.expire_all()
    documento = db_session.query(Documento).filter_by(id=salida["id"]).one()
    assert documento.estado == "listo"
    assert documento.error_detalle is None
    fragmentos = (
        db_session.query(DocumentoChunk).filter_by(documento_id=documento.id).all()
    )
    assert len(fragmentos) >= 1
    # Todo fragmento hereda el portal del documento (aislamiento).
    for f in fragmentos:
        assert f.portal_id == documento.portal_id


def test_subida_de_formato_no_admitido_devuelve_422(client, auth, con_embedder_bueno):
    r = client.post(
        "/api/admin/documentos",
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 8,
        headers={**auth, "Content-Type": "image/png"},
    )
    assert r.status_code == 422


def test_subida_de_archivo_vacio_devuelve_422(client, auth, con_embedder_bueno):
    r = client.post(
        "/api/admin/documentos",
        content=b"",
        headers={**auth, "Content-Type": "text/plain"},
    )
    assert r.status_code == 422


def test_idioma_invalido_devuelve_422(client, auth, con_embedder_bueno):
    r = client.post(
        "/api/admin/documentos?idioma=fr",
        content=b"hola",
        headers={**auth, "Content-Type": "text/plain"},
    )
    assert r.status_code == 422


# --- Transiciones de estado ------------------------------------------------


def test_fallo_del_embedder_marca_error_sin_fragmentos(
    client, auth, con_embedder_que_falla, db_session,
):
    r = _subir_txt(client, auth)
    assert r.status_code == 201
    doc_id = r.json()["id"]
    db_session.expire_all()
    documento = db_session.query(Documento).filter_by(id=doc_id).one()
    assert documento.estado == "error"
    assert documento.error_detalle  # detalle legible
    # No quedan fragmentos parciales del documento.
    assert (
        db_session.query(DocumentoChunk).filter_by(documento_id=doc_id).count() == 0
    )


# --- Listado, GET y borrado ------------------------------------------------


def test_listado_devuelve_solo_del_portal(client, auth, con_embedder_bueno):
    _subir_txt(client, auth, nombre="a.txt")
    _subir_txt(client, auth, nombre="b.txt")
    r = client.get("/api/admin/documentos", headers=auth)
    assert r.status_code == 200
    lista = r.json()
    assert {d["nombre"] for d in lista} == {"a.txt", "b.txt"}


def test_borrado_elimina_documento_y_sus_fragmentos(
    client, auth, con_embedder_bueno, db_session,
):
    doc_id = _subir_txt(client, auth).json()["id"]
    r = client.delete(f"/api/admin/documentos/{doc_id}", headers=auth)
    assert r.status_code == 204
    db_session.expire_all()
    assert db_session.query(Documento).filter_by(id=doc_id).first() is None
    assert (
        db_session.query(DocumentoChunk).filter_by(documento_id=doc_id).count() == 0
    )


# --- Autorización (niveles) ------------------------------------------------


def test_editor_no_puede_subir(client, editor_auth, con_embedder_bueno):
    r = _subir_txt(client, editor_auth)
    assert r.status_code == 403


def test_editor_no_puede_listar(client, editor_auth, con_embedder_bueno):
    assert client.get("/api/admin/documentos", headers=editor_auth).status_code == 403


def test_anonimo_no_puede_subir(client, con_embedder_bueno):
    r = client.post(
        "/api/admin/documentos",
        content=b"hola",
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 401


# --- Aislamiento por portal ------------------------------------------------


@pytest.fixture
def hacer_cliente(db_session):
    """Fábrica de clientes por host, compartiendo la misma sesión de base de datos.

    Levanta también el segundo portal, para que ambos existan durante la prueba.
    """
    sembrar_portal_secundario(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield lambda host: TestClient(app, base_url=f"http://{host}")
    app.dependency_overrides.clear()


def _auth(cliente, email: str, password: str) -> dict:
    r = cliente.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_documento_de_otro_portal_responde_404(
    hacer_cliente, con_embedder_bueno, db_session,
):
    # Portal A sube; Portal B intenta ver por id directo → 404 (no revela existencia).
    cliente_a = hacer_cliente("localhost")
    auth_a = _auth(cliente_a, ADMIN_EMAIL, ADMIN_PASSWORD)
    doc_id_a = _subir_txt(cliente_a, auth_a, nombre="privado.txt").json()["id"]

    cliente_b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_b = _auth(cliente_b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)
    assert cliente_b.get(f"/api/admin/documentos/{doc_id_a}", headers=auth_b).status_code == 404
    assert cliente_b.delete(f"/api/admin/documentos/{doc_id_a}", headers=auth_b).status_code == 404


def test_listado_acotado_al_portal(hacer_cliente, con_embedder_bueno):
    cliente_a = hacer_cliente("localhost")
    auth_a = _auth(cliente_a, ADMIN_EMAIL, ADMIN_PASSWORD)
    _subir_txt(cliente_a, auth_a, nombre="portal-a.txt")

    cliente_b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_b = _auth(cliente_b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)
    r = cliente_b.get("/api/admin/documentos", headers=auth_b)
    assert r.status_code == 200
    assert r.json() == []  # portal B no ve el documento del portal A


# --- Re-embedido de artículos ---------------------------------------------


def test_crear_articulo_reindexa_por_idioma(
    client, auth, con_embedder_bueno, db_session,
):
    r = client.post("/api/admin/articulos", json=articulo_valido("otro-articulo"), headers=auth)
    assert r.status_code == 201
    db_session.expire_all()
    chunks = (
        db_session.query(ArticuloChunk)
        .filter_by(articulo_id="otro-articulo")
        .all()
    )
    # Al menos un fragmento por idioma (es/pt); el artículo cabe en uno solo.
    idiomas_indexados = {c.idioma for c in chunks}
    assert idiomas_indexados == {"es", "pt"}


def test_borrar_articulo_borra_sus_fragmentos(
    client, auth, con_embedder_bueno, db_session,
):
    client.post("/api/admin/articulos", json=articulo_valido("borrar-me"), headers=auth)
    db_session.expire_all()
    assert (
        db_session.query(ArticuloChunk).filter_by(articulo_id="borrar-me").count() > 0
    )
    assert client.delete("/api/admin/articulos/borrar-me", headers=auth).status_code == 204
    db_session.expire_all()
    assert (
        db_session.query(ArticuloChunk).filter_by(articulo_id="borrar-me").count() == 0
    )
