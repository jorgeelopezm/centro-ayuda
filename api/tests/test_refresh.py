"""Refresh token: rotación, detección de reutilización y revocación."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import AdminUser, RefreshToken
from app.security import hash_refresh
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, EDITOR_EMAIL, EDITOR_PASSWORD


def _login(client, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> tuple[str, str]:
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    return cuerpo["access_token"], cuerpo["refresh_token"]


def test_login_devuelve_refresh_token(client):
    _, refresh = _login(client)
    assert refresh


def test_refresh_rota_y_renueva(client):
    _, r1 = _login(client)

    resp = client.post("/api/auth/refresh", json={"refresh_token": r1})
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["access_token"]
    r2 = cuerpo["refresh_token"]
    assert r2 and r2 != r1

    # La cadena de rotación continúa: el token nuevo renueva y emite otro.
    resp2 = client.post("/api/auth/refresh", json={"refresh_token": r2})
    assert resp2.status_code == 200, resp2.text
    r3 = resp2.json()["refresh_token"]
    assert r3 and r3 != r2


def test_reutilizacion_revoca_la_familia(client):
    _, r1 = _login(client)
    r2 = client.post("/api/auth/refresh", json={"refresh_token": r1}).json()["refresh_token"]

    # Replay del token ya rotado: se detecta reutilización.
    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 401
    # Y la familia entera queda revocada: el token legítimo posterior también cae.
    assert client.post("/api/auth/refresh", json={"refresh_token": r2}).status_code == 401


def test_refresh_token_invalido_rechazado(client):
    assert client.post("/api/auth/refresh", json={"refresh_token": "basura"}).status_code == 401


def test_refresh_sin_campo_es_422(client):
    assert client.post("/api/auth/refresh", json={}).status_code == 422


def test_logout_revoca_el_refresh(client):
    _, r1 = _login(client)
    assert client.post("/api/auth/logout", json={"refresh_token": r1}).status_code == 200
    # Tras el logout, el refresh token ya no renueva.
    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 401


def test_refresh_expirado_rechazado(client, db_session):
    _, r1 = _login(client)

    fila = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh(r1))
        .one()
    )
    fila.expira = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 401


def test_refresh_de_usuario_desactivado_rechazado(client, db_session):
    _, r1 = _login(client, EDITOR_EMAIL, EDITOR_PASSWORD)

    usuario = db_session.query(AdminUser).filter(AdminUser.email == EDITOR_EMAIL).one()
    usuario.activo = False
    db_session.commit()

    assert client.post("/api/auth/refresh", json={"refresh_token": r1}).status_code == 401
