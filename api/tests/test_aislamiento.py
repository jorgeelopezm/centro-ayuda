"""Aislamiento por portal: un portal nunca lee ni escribe datos de otro.

El portal se resuelve por el host de cada petición. Estas pruebas levantan dos portales
(`default` en `localhost` y un segundo en `otra-marca.test`) y comprueban que el
contenido, los usuarios, el panel y la marca de uno no se filtran al otro, y que el
acceso por id directo a un recurso de otro portal responde 404 (no revela su existencia).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import AdminUser
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    SEGUNDO_ADMIN_PASSWORD,
    SEGUNDO_PORTAL_HOST,
    SEGUNDO_PORTAL_UUID,
    articulo_valido,
    sembrar_portal_secundario,
)

# PNG mínimo: basta la firma para que la detección por *magic bytes* lo acepte.
PNG_VALIDO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


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


def _auth(cliente: TestClient, email: str, password: str) -> dict:
    r = cliente.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Contenido y marca (público) ---------------------------------------------

def test_el_contenido_publico_no_se_mezcla_entre_portales(hacer_cliente):
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)

    contenido_a = a.get("/api/es/contenido").json()
    contenido_b = b.get("/api/es/contenido").json()

    # El portal `default` tiene su categoría "cuenta" (nombre "Cuenta") y la empresa "Acme".
    assert contenido_a["empresa"] == "Acme"
    cat_a = {c["id"]: c["nombre"] for c in contenido_a["categorias"]}
    assert cat_a["cuenta"] == "Cuenta"

    # El segundo portal NO ve la marca ni los artículos del `default`. Comparte el id de
    # categoría "cuenta" (mismo id, filas distintas por la PK compuesta), pero servida con
    # SU nombre ("Cuenta B"): la categoría de un portal no se filtra al otro.
    assert contenido_b["empresa"] != "Acme"
    cat_b = {c["id"]: c["nombre"] for c in contenido_b["categorias"]}
    assert cat_b["cuenta"] == "Cuenta B"
    assert contenido_b["articulos"] == []


# --- Artículos ---------------------------------------------------------------

def test_un_articulo_de_otro_portal_no_se_lee_por_id_directo(hacer_cliente):
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = _auth(a, ADMIN_EMAIL, ADMIN_PASSWORD)
    auth_b = _auth(b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)

    # El portal A crea un artículo.
    creado = a.post("/api/admin/articulos", json=articulo_valido("solo-de-a"), headers=auth_a)
    assert creado.status_code == 201, creado.text

    # El portal B ni lo lista ni lo alcanza por id directo (404, no revela existencia).
    assert b.get("/api/admin/articulos", headers=auth_b).json() == []
    assert b.get("/api/admin/articulos/solo-de-a", headers=auth_b).status_code == 404

    # Sanidad: para su propio portal sí existe.
    assert a.get("/api/admin/articulos/solo-de-a", headers=auth_a).status_code == 200


def test_dos_portales_pueden_reusar_el_mismo_id_de_articulo(hacer_cliente):
    # El id de artículo es único *por portal* (PK compuesta `(portal_id, id)`), no global:
    # dos portales pueden crear un artículo con el MISMO id sin colisionar. Con el id PK
    # global anterior, el segundo chocaba en la PK (422) y esa diferencia 201/422 dejaba
    # además enumerar qué ids existían en cualquier portal (oráculo cross-tenant).
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = _auth(a, ADMIN_EMAIL, ADMIN_PASSWORD)
    auth_b = _auth(b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)

    # Mismo id "comun" en ambos portales: los dos crean con 201 (cada uno contra su
    # propia categoría "cuenta").
    assert a.post("/api/admin/articulos", json=articulo_valido("comun"), headers=auth_a).status_code == 201
    assert b.post("/api/admin/articulos", json=articulo_valido("comun"), headers=auth_b).status_code == 201

    # Cada portal alcanza SU artículo por ese id compartido, sin ver el del otro: el id no
    # los cruza (mismos ids, filas distintas por portal).
    art_a = a.get("/api/admin/articulos/comun", headers=auth_a)
    art_b = b.get("/api/admin/articulos/comun", headers=auth_b)
    assert art_a.status_code == 200 and art_b.status_code == 200
    assert art_a.json()["es"]["slug"] == art_b.json()["es"]["slug"] == "comun-es"


# --- Paridad es/pt por portal ------------------------------------------------

def test_la_paridad_es_pt_se_mantiene_por_portal(hacer_cliente):
    # La paridad es/pt es un invariante *por portal*: cada portal publica los mismos
    # artículos en ambos idiomas, sin mezclar los de otro. El CRUD bilingüe atómico
    # (crear exige es+pt juntos) la sostiene en cada portal por separado.
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = _auth(a, ADMIN_EMAIL, ADMIN_PASSWORD)
    auth_b = _auth(b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)

    # Cada portal crea, por el panel, su propio artículo bilingüe (distinto entre sí).
    assert a.post("/api/admin/articulos", json=articulo_valido("solo-de-a"), headers=auth_a).status_code == 201
    assert b.post("/api/admin/articulos", json=articulo_valido("solo-de-b"), headers=auth_b).status_code == 201

    # Dentro de cada portal, es y pt publican exactamente los mismos ids (paridad), y
    # ninguno ve el artículo del otro (aislamiento). Se comprueban ambos portales para
    # que la paridad no quede probada solo de forma vacía sobre un portal sin artículos.
    for cliente, propio, ajeno in ((a, "solo-de-a", "solo-de-b"), (b, "solo-de-b", "solo-de-a")):
        ids_es = [x["id"] for x in cliente.get("/api/es/contenido").json()["articulos"]]
        ids_pt = [x["id"] for x in cliente.get("/api/pt/contenido").json()["articulos"]]
        assert ids_es == ids_pt == [propio]
        assert ajeno not in ids_es


# --- Usuarios ----------------------------------------------------------------

def test_los_usuarios_de_un_portal_no_se_ven_desde_otro(hacer_cliente, db_session):
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = _auth(a, ADMIN_EMAIL, ADMIN_PASSWORD)

    # El listado de A solo trae los usuarios de A (Administrador + Editor del seed).
    correos_a = {u["email"] for u in a.get("/api/admin/usuarios", headers=auth_a).json()}
    assert correos_a == {ADMIN_EMAIL, "editor@test.local"}

    # El Administrador de B no aparece, y actuar sobre su id directo da 404 desde A
    # (no revela su existencia). Se usa `activar`, que sí existe como ruta por id.
    admin_b = (
        db_session.query(AdminUser).filter(AdminUser.portal_id == SEGUNDO_PORTAL_UUID).first()
    )
    assert a.post(f"/api/admin/usuarios/{admin_b.id}/activar", headers=auth_a).status_code == 404


# --- Panel -------------------------------------------------------------------

def test_las_preguntas_sin_resolver_son_por_portal(hacer_cliente):
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = _auth(a, ADMIN_EMAIL, ADMIN_PASSWORD)
    auth_b = _auth(b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)

    # El seed deja una pregunta en A; B no tiene ninguna.
    assert len(a.get("/api/admin/preguntas-sin-resolver", headers=auth_a).json()) == 1
    assert b.get("/api/admin/preguntas-sin-resolver", headers=auth_b).json() == []


# --- Logotipo ----------------------------------------------------------------

def test_el_logo_de_un_portal_no_se_sirve_en_otro(hacer_cliente):
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = _auth(a, ADMIN_EMAIL, ADMIN_PASSWORD)

    # A sube un logo; B no tiene ninguno.
    assert a.post("/api/admin/ajustes/logo", content=PNG_VALIDO, headers=auth_a).status_code == 201
    assert a.get("/api/marca/logo").status_code == 200
    # El logo de A no se sirve en el host de B (404, no se filtra el binario).
    assert b.get("/api/marca/logo").status_code == 404


def test_la_plantilla_de_un_portal_no_se_filtra_a_otro(hacer_cliente):
    # Cada portal publica SU plantilla. El segundo portal aún no tiene fila de ajustes, así
    # que al elegir plantilla el endpoint se la crea (id propio, autoincremental), sin
    # chocar con la del `default` ni contaminarla.
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = _auth(a, ADMIN_EMAIL, ADMIN_PASSWORD)
    auth_b = _auth(b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)

    assert a.put(
        "/api/admin/ajustes/plantilla", json={"plantilla": "documentacion"}, headers=auth_a
    ).status_code == 200
    assert b.put(
        "/api/admin/ajustes/plantilla", json={"plantilla": "default"}, headers=auth_b
    ).status_code == 200

    # A publica `documentacion`; B sigue con `default` (la elección de A no lo toca).
    assert a.get("/api/es/contenido").json()["plantilla"] == "documentacion"
    assert b.get("/api/es/contenido").json()["plantilla"] == "default"


def test_el_segundo_portal_edita_su_marca_sin_colisionar_ni_filtrarse(hacer_cliente):
    # El segundo portal aún no tiene fila de ajustes: al editar su marca la crea con id
    # propio (autoincremental), sin chocar con la del `default` ni contaminarla.
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_b = _auth(b, ADMIN_EMAIL, SEGUNDO_ADMIN_PASSWORD)

    assert b.put("/api/admin/ajustes/empresa", json={"empresa": "Marca B"}, headers=auth_b).status_code == 200
    assert b.post("/api/admin/ajustes/logo", content=PNG_VALIDO, headers=auth_b).status_code == 201

    # B ve su propia marca; A (default) conserva la suya y no hereda el logo de B.
    assert b.get("/api/es/contenido").json()["empresa"] == "Marca B"
    assert a.get("/api/es/contenido").json()["empresa"] == "Acme"
    assert b.get("/api/marca/logo").status_code == 200
    assert a.get("/api/marca/logo").status_code == 404


# --- Sesión ------------------------------------------------------------------

def test_una_credencial_no_cruza_de_portal(hacer_cliente):
    # Mismo correo en ambos portales, pero contraseñas distintas: la contraseña del
    # Administrador de A no inicia sesión en el host de B (se usa el usuario de B).
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    r = b.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 401
    # Con la contraseña propia de B, sí inicia sesión.
    ok = b.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": SEGUNDO_ADMIN_PASSWORD})
    assert ok.status_code == 200


def test_un_access_token_de_un_portal_no_autoriza_en_otro(hacer_cliente):
    # El mismo correo existe en A y en B. Un access token emitido en A, presentado en el
    # host de B, NO debe autenticar al homónimo de B: el token lleva el portal en el que
    # se emitió y `admin_actual` exige que coincida con el portal del host. Sin esto, un
    # token robado (o simplemente reusado) cruzaría de portal aunque las contraseñas
    # difieran, porque el atacante no necesita la contraseña de B: le basta el token de A.
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    login_a = a.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert login_a.status_code == 200, login_a.text
    cab = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

    # En su propio portal el token vale; en el host de B responde 401 (sesión de otro portal).
    assert a.get("/api/admin/articulos", headers=cab).status_code == 200
    assert b.get("/api/admin/articulos", headers=cab).status_code == 401


def test_un_refresh_de_un_portal_no_renueva_en_otro(hacer_cliente):
    # El refresh token tampoco cruza de portal: renovar en el host de B con un refresh de
    # A responde 401 y —al no quemarse— la sesión legítima de A sigue pudiendo renovar.
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    login_a = a.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert login_a.status_code == 200, login_a.text
    refresh_a = login_a.json()["refresh_token"]

    # En el host de B el refresh de A no renueva (401) y no se consume.
    assert b.post("/api/auth/refresh", json={"refresh_token": refresh_a}).status_code == 401
    # En su propio host sí renueva: la sesión legítima quedó intacta (no se quemó).
    assert a.post("/api/auth/refresh", json={"refresh_token": refresh_a}).status_code == 200


# --- Host desconocido / portal suspendido ------------------------------------

def test_host_desconocido_responde_404(hacer_cliente):
    desconocido = hacer_cliente("nadie.example")
    assert desconocido.get("/api/es/contenido").status_code == 404
