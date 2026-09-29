"""Traducción asistida por IA del nombre de categoría: borrador sin persistir,
con proveedor sustituido. Espejo de `test_traduccion.py` para artículos, acotado
al contenido de categoría (spec `traduccion-ia-categorias`)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.servicios_ia import ProveedorNoConfigurado, obtener_traductor
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    SEGUNDO_ADMIN_PASSWORD,
    SEGUNDO_PORTAL_HOST,
    sembrar_portal_secundario,
)


@pytest.fixture
def hacer_cliente(db_session):
    """Fábrica de clientes por host, compartiendo la misma sesión de base de datos
    (mismo patrón que `test_aislamiento.py`). Levanta también el segundo portal."""
    sembrar_portal_secundario(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield lambda host: TestClient(app, base_url=f"http://{host}")
    app.dependency_overrides.clear()


class ProveedorFalsoCategoria:
    """Doble de proveedor: no llama a la red. Devuelve un nombre «traducido»
    reconocible y registra la dirección con la que se le llamó."""

    def __init__(self) -> None:
        self.llamado_con: tuple[str, str] | None = None

    def traducir(self, origen: str, destino: str, contenido: dict) -> dict:
        self.llamado_con = (origen, destino)
        return {
            "slug": "no-deberia-usarse",  # el servicio conserva el slug de origen
            "nombre": f"[{destino}] {contenido['nombre']}",
        }


CONTENIDO_ES = {"slug": "facturacion", "nombre": "Facturación"}


@pytest.fixture
def proveedor_falso():
    falso = ProveedorFalsoCategoria()
    app.dependency_overrides[obtener_traductor] = lambda: falso
    yield falso
    app.dependency_overrides.pop(obtener_traductor, None)


def test_traduce_es_a_pt_como_borrador(client, auth, proveedor_falso):
    r = client.post(
        "/api/admin/categorias/traducir",
        json={"origen": "es", "contenido": CONTENIDO_ES},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert proveedor_falso.llamado_con == ("es", "pt")
    assert cuerpo["nombre"] == "[pt] Facturación"
    # El slug no se traduce: se conserva el del contenido de origen.
    assert cuerpo["slug"] == "facturacion"


def test_traduce_pt_a_es(client, auth, proveedor_falso):
    contenido_pt = {"slug": "faturamento", "nombre": "Faturamento"}
    r = client.post(
        "/api/admin/categorias/traducir",
        json={"origen": "pt", "contenido": contenido_pt},
        headers=auth,
    )
    assert r.status_code == 200
    assert proveedor_falso.llamado_con == ("pt", "es")
    assert r.json()["nombre"] == "[es] Faturamento"


def test_editor_puede_traducir(client, editor_auth, proveedor_falso):
    r = client.post(
        "/api/admin/categorias/traducir",
        json={"origen": "es", "contenido": CONTENIDO_ES},
        headers=editor_auth,
    )
    assert r.status_code == 200


def test_anonimo_no_puede_traducir(client):
    r = client.post(
        "/api/admin/categorias/traducir",
        json={"origen": "es", "contenido": CONTENIDO_ES},
    )
    assert r.status_code == 401


def test_sin_proveedor_configurado_da_409(client, auth):
    """Sin fila de ConfigIA ni clave, el traductor real corta con 409 (el Administrador
    debe configurar). No se sustituye la dependencia: se ejerce la resolución real."""

    def traductor_sin_config():
        raise ProveedorNoConfigurado("anthropic")

    app.dependency_overrides[obtener_traductor] = traductor_sin_config
    try:
        r = client.post(
            "/api/admin/categorias/traducir",
            json={"origen": "es", "contenido": CONTENIDO_ES},
            headers=auth,
        )
        assert r.status_code == 409
    finally:
        app.dependency_overrides.pop(obtener_traductor, None)


def test_disponible_igual_en_cualquier_portal(hacer_cliente, proveedor_falso):
    """El endpoint no lee ni escribe nada específico de un portal (es puramente un
    proxy stateless al proveedor de traducción): la sesión de cada portal lo alcanza
    igual, sin que uno filtre o bloquee al otro."""
    a = hacer_cliente("localhost")
    b = hacer_cliente(SEGUNDO_PORTAL_HOST)
    auth_a = {
        "Authorization": f"Bearer {a.post('/api/auth/login', json={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD}).json()['access_token']}"
    }
    auth_b = {
        "Authorization": f"Bearer {b.post('/api/auth/login', json={'email': ADMIN_EMAIL, 'password': SEGUNDO_ADMIN_PASSWORD}).json()['access_token']}"
    }

    r_a = a.post(
        "/api/admin/categorias/traducir", json={"origen": "es", "contenido": CONTENIDO_ES}, headers=auth_a
    )
    r_b = b.post(
        "/api/admin/categorias/traducir", json={"origen": "es", "contenido": CONTENIDO_ES}, headers=auth_b
    )
    assert r_a.status_code == 200
    assert r_b.status_code == 200
