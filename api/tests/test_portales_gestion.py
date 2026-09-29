"""Gestión de portales por el SuperAdmin (`/api/admin/portales`).

Cubre la Sección 6 del cambio `multi-tenant-portales`: alta con su Administrador, listado,
suspensión/reactivación reversible, validaciones de slug y el blindaje por nivel (solo
SuperAdmin; un Administrador de portal recibe 403).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.servicios import PORTAL_DEFECTO_SLUG, PORTAL_DEFECTO_UUID

# El host de un portal recién creado es `<slug>.<base_domain>`; el base_domain de test es
# el de por defecto (`tuapp.com`), ya que conftest no lo sobrescribe.
BASE_DOMAIN = "tuapp.com"

NUEVO_SLUG = "cliente-nuevo"
NUEVO_ADMIN_EMAIL = "admin@cliente-nuevo.local"
NUEVO_ADMIN_PASSWORD = "contrasena-del-nuevo-admin"


def _payload(slug: str = NUEVO_SLUG) -> dict:
    return {
        "slug": slug,
        "nombreEmpresa": "Cliente Nuevo",
        "adminEmail": NUEVO_ADMIN_EMAIL,
        "adminPassword": NUEVO_ADMIN_PASSWORD,
    }


# --- Autorización por nivel --------------------------------------------------

def test_administrador_de_portal_no_gestiona_portales(client, auth):
    # El Administrador (nivel 3) del portal `default` no alcanza la gestión de portales.
    assert client.get("/api/admin/portales", headers=auth).status_code == 403
    assert client.post("/api/admin/portales", headers=auth, json=_payload()).status_code == 403


def test_sin_sesion_no_se_gestionan_portales(superadmin_client):
    # Sin credenciales, 401 (el host resuelve al portal de plataforma, pero falta sesión).
    assert superadmin_client.get("/api/admin/portales").status_code == 401


# --- Listado -----------------------------------------------------------------

def test_superadmin_lista_los_portales_de_contenido(superadmin_client, superadmin_auth):
    r = superadmin_client.get("/api/admin/portales", headers=superadmin_auth)
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()]
    # Ve el portal `default`; el de plataforma NO aparece (no es gestionable). El `id`
    # que devuelve la API es texto (UUID serializado), así que se compara como texto.
    assert str(PORTAL_DEFECTO_UUID) in ids
    assert "platform" not in ids


# --- Alta --------------------------------------------------------------------

def test_superadmin_crea_portal_con_su_administrador(superadmin_client, superadmin_auth):
    r = superadmin_client.post("/api/admin/portales", headers=superadmin_auth, json=_payload())
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["slug"] == NUEVO_SLUG
    assert cuerpo["estado"] == "activo"
    assert cuerpo["host"] == f"{NUEVO_SLUG}.{BASE_DOMAIN}"
    assert cuerpo["adminEmail"] == NUEVO_ADMIN_EMAIL

    # El portal nace con su host, así que su Administrador puede iniciar sesión ahí.
    en_el_nuevo = TestClient(app, base_url=f"http://{NUEVO_SLUG}.{BASE_DOMAIN}")
    login = en_el_nuevo.post(
        "/api/auth/login", json={"email": NUEVO_ADMIN_EMAIL, "password": NUEVO_ADMIN_PASSWORD}
    )
    assert login.status_code == 200, login.text
    # Y ese Administrador ve su propio nombre de empresa en el contenido público del portal.
    contenido = en_el_nuevo.get("/api/es/contenido")
    assert contenido.status_code == 200
    assert contenido.json()["empresa"] == "Cliente Nuevo"


def test_el_id_del_portal_creado_es_uuid_distinto_del_slug(superadmin_client, superadmin_auth):
    # `Portal.id` es un UUID opaco separado del `slug` (migración `0012_portal_uuid`):
    # nunca coincide con el slug legible, a diferencia del modelo anterior (`id == slug`).
    r = superadmin_client.post("/api/admin/portales", headers=superadmin_auth, json=_payload())
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["id"] != cuerpo["slug"]
    assert uuid.UUID(cuerpo["id"]) is not None


def test_el_administrador_del_nuevo_portal_no_gestiona_portales(superadmin_client, superadmin_auth):
    # Nace como Administrador (nivel 3), no SuperAdmin: no puede gestionar portales.
    superadmin_client.post("/api/admin/portales", headers=superadmin_auth, json=_payload())
    en_el_nuevo = TestClient(app, base_url=f"http://{NUEVO_SLUG}.{BASE_DOMAIN}")
    token = en_el_nuevo.post(
        "/api/auth/login", json={"email": NUEVO_ADMIN_EMAIL, "password": NUEVO_ADMIN_PASSWORD}
    ).json()["access_token"]
    r = en_el_nuevo.get("/api/admin/portales", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


# --- Validaciones de slug ----------------------------------------------------

def test_slug_duplicado_se_rechaza(superadmin_client, superadmin_auth):
    # `default` ya existe como portal (por su slug: id y slug ya no son lo mismo).
    r = superadmin_client.post(
        "/api/admin/portales", headers=superadmin_auth, json=_payload(slug=PORTAL_DEFECTO_SLUG)
    )
    assert r.status_code == 409


def test_slug_reservado_se_rechaza(superadmin_client, superadmin_auth):
    r = superadmin_client.post("/api/admin/portales", headers=superadmin_auth, json=_payload(slug="www"))
    assert r.status_code == 409


def test_slug_con_formato_invalido_se_rechaza(superadmin_client, superadmin_auth):
    # Mayúsculas, espacios o guion al borde: el esquema los rechaza con 422.
    for malo in ("Cliente", "con espacio", "-borde", "borde-", "a"):
        r = superadmin_client.post("/api/admin/portales", headers=superadmin_auth, json=_payload(slug=malo))
        assert r.status_code == 422, f"esperado 422 para slug {malo!r}, fue {r.status_code}"


def test_contrasena_debil_del_admin_se_rechaza(superadmin_client, superadmin_auth):
    datos = _payload()
    datos["adminPassword"] = "corta"
    r = superadmin_client.post("/api/admin/portales", headers=superadmin_auth, json=datos)
    assert r.status_code == 422


# --- Suspensión y reactivación -----------------------------------------------

def test_suspender_veta_el_portal_y_reactivar_lo_restaura(superadmin_client, superadmin_auth):
    en_default = TestClient(app, base_url="http://localhost")
    # Antes de suspender, el contenido del portal `default` responde 200.
    assert en_default.get("/api/es/contenido").status_code == 200

    r = superadmin_client.post(
        f"/api/admin/portales/{PORTAL_DEFECTO_UUID}/suspender", headers=superadmin_auth
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "suspendido"
    # Suspendido: el contenido queda inaccesible (503) sin haberse borrado.
    assert en_default.get("/api/es/contenido").status_code == 503

    r = superadmin_client.post(
        f"/api/admin/portales/{PORTAL_DEFECTO_UUID}/reactivar", headers=superadmin_auth
    )
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "activo"
    # Reactivado: vuelve a estar disponible, con sus datos intactos.
    assert en_default.get("/api/es/contenido").status_code == 200


def test_no_se_puede_suspender_el_portal_de_plataforma(superadmin_client, superadmin_auth):
    # El portal de plataforma no es gestionable: 404 (ni siquiera se revela). Así el
    # SuperAdmin no puede cerrarse su propia puerta.
    r = superadmin_client.post("/api/admin/portales/platform/suspender", headers=superadmin_auth)
    assert r.status_code == 404


def test_suspender_portal_inexistente_es_404(superadmin_client, superadmin_auth):
    r = superadmin_client.post("/api/admin/portales/no-existe/suspender", headers=superadmin_auth)
    assert r.status_code == 404
