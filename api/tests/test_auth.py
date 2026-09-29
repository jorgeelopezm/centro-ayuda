"""Login, logout y protección de las rutas de administración."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.models import AdminUser
from app.security import crear_token, decodificar_token
from app.servicios import PORTAL_DEFECTO_UUID
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD


def test_login_valido_devuelve_token(client):
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_devuelve_tipo_bearer(client):
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.json()["token_type"] == "bearer"


def test_login_invalido_es_generico(client):
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "incorrecta"})
    assert r.status_code == 401
    # El mensaje no revela si falló el correo o la contraseña.
    assert "contraseña" in r.json()["detail"].lower()


def test_login_con_correo_inexistente_da_el_mismo_mensaje(client):
    fallo_correo = client.post("/api/auth/login", json={"email": "nadie@test.local", "password": ADMIN_PASSWORD})
    fallo_clave = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "incorrecta"})

    # Correo inexistente y contraseña incorrecta son indistinguibles desde fuera.
    assert fallo_correo.status_code == fallo_clave.status_code == 401
    assert fallo_correo.json()["detail"] == fallo_clave.json()["detail"]


def test_login_sin_campos_es_422(client):
    assert client.post("/api/auth/login", json={}).status_code == 422


def test_login_de_usuario_desactivado_rechazado(client, db_session):
    usuario = db_session.query(AdminUser).filter(AdminUser.email == ADMIN_EMAIL).one()
    usuario.activo = False
    db_session.commit()

    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 401
    # Mismo mensaje genérico que una contraseña incorrecta: no revela el estado de la cuenta.
    assert "contraseña" in r.json()["detail"].lower()


def test_el_token_emitido_identifica_al_administrador(token):
    datos = decodificar_token(token)
    assert datos is not None
    assert datos.email == ADMIN_EMAIL
    # El token queda atado al portal del host donde se emitió (`default` en los tests).
    # `datos.portal_id` es texto (`crear_token` serializa el UUID); se compara como tal.
    assert datos.portal_id == str(PORTAL_DEFECTO_UUID)


def test_admin_sin_token_rechazado(client):
    r = client.get("/api/admin/articulos")
    assert r.status_code == 401


def test_admin_con_token_invalido_rechazado(client):
    r = client.get("/api/admin/articulos", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401


def test_admin_con_token_caducado_rechazado(client):
    s = get_settings()
    caducado = jwt.encode(
        {"sub": ADMIN_EMAIL, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        s.jwt_secret,
        algorithm=s.jwt_algorithm,
    )
    r = client.get("/api/admin/articulos", headers={"Authorization": f"Bearer {caducado}"})
    assert r.status_code == 401


def test_admin_con_token_de_usuario_inexistente_rechazado(client):
    # Token bien firmado, pero de un administrador que no está en la base.
    fantasma = crear_token("fantasma@test.local", str(PORTAL_DEFECTO_UUID))
    r = client.get("/api/admin/articulos", headers={"Authorization": f"Bearer {fantasma}"})
    assert r.status_code == 401


def test_esquema_de_autorizacion_distinto_de_bearer_rechazado(client):
    r = client.get("/api/admin/articulos", headers={"Authorization": "Basic YWRtaW46eA=="})
    assert r.status_code == 401


def test_logout_con_sesion(client, auth):
    r = client.post("/api/auth/logout", headers=auth)
    assert r.status_code == 200
    assert r.json() == {"detail": "Sesión cerrada"}


def test_logout_sin_cuerpo_siempre_cierra(client):
    # El logout no exige sesión: siempre debe poder cerrar (idempotente). El BFF
    # borra las cookies aunque el refresh ya no sea válido.
    assert client.post("/api/auth/logout").status_code == 200


def test_logout_no_revoca_el_access_token(client, auth):
    client.post("/api/auth/logout", headers=auth)
    # El logout revoca la familia del refresh token (ver test_refresh), pero el
    # access token es un JWT corto sin lista de revocación: sigue válido hasta
    # expirar. La sesión real se corta al no poder renovarlo.
    assert client.get("/api/admin/articulos", headers=auth).status_code == 200
