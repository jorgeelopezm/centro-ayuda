"""Gestión de usuarios (solo Administrador) y sus salvaguardas."""

from __future__ import annotations

from tests.conftest import ADMIN_EMAIL, EDITOR_EMAIL

NUEVO = {"email": "nuevo@test.local", "password": "contrasena-larga-de-prueba", "nivel": 2}


def _id_por_correo(client, auth, correo: str) -> int:
    usuarios = client.get("/api/admin/usuarios", headers=auth).json()
    return next(u["id"] for u in usuarios if u["email"] == correo)


def test_administrador_lista_usuarios_sin_exponer_el_hash(client, auth):
    r = client.get("/api/admin/usuarios", headers=auth)
    assert r.status_code == 200
    cuerpo = r.json()
    correos = {u["email"] for u in cuerpo}
    assert {ADMIN_EMAIL, EDITOR_EMAIL} <= correos
    assert all("password_hash" not in u and "password" not in u for u in cuerpo)


def test_administrador_crea_un_editor_que_puede_iniciar_sesion(client, auth):
    r = client.post("/api/admin/usuarios", json=NUEVO, headers=auth)
    assert r.status_code == 201
    assert r.json()["nivel"] == 2 and r.json()["activo"] is True

    login = client.post("/api/auth/login", json={"email": NUEVO["email"], "password": NUEVO["password"]})
    assert login.status_code == 200


def test_crear_con_correo_repetido_da_409(client, auth):
    dup = {"email": ADMIN_EMAIL, "password": "contrasena-larga-de-prueba", "nivel": 2}
    assert client.post("/api/admin/usuarios", json=dup, headers=auth).status_code == 409


def test_crear_con_contrasena_corta_da_422(client, auth):
    corta = {"email": "corta@test.local", "password": "corta", "nivel": 2}
    assert client.post("/api/admin/usuarios", json=corta, headers=auth).status_code == 422


def test_crear_con_nivel_no_asignable_da_422(client, auth):
    # Anónimo (1) no es un nivel asignable; solo Editor (2) o Administrador (3).
    mal = {"email": "mal@test.local", "password": "contrasena-larga-de-prueba", "nivel": 1}
    assert client.post("/api/admin/usuarios", json=mal, headers=auth).status_code == 422


def test_administrador_edita_el_nivel_de_un_usuario(client, auth):
    editor = _id_por_correo(client, auth, EDITOR_EMAIL)
    r = client.put(f"/api/admin/usuarios/{editor}", json={"email": EDITOR_EMAIL, "nivel": 3}, headers=auth)
    assert r.status_code == 200 and r.json()["nivel"] == 3


def test_desactivar_y_reactivar_a_un_usuario(client, auth):
    editor = _id_por_correo(client, auth, EDITOR_EMAIL)
    assert client.post(f"/api/admin/usuarios/{editor}/desactivar", headers=auth).json()["activo"] is False
    assert client.post(f"/api/admin/usuarios/{editor}/activar", headers=auth).json()["activo"] is True


def test_administrador_no_puede_autodesactivarse(client, auth):
    administrador = _id_por_correo(client, auth, ADMIN_EMAIL)
    assert client.post(f"/api/admin/usuarios/{administrador}/desactivar", headers=auth).status_code == 409


def test_administrador_no_puede_autodegradarse(client, auth):
    administrador = _id_por_correo(client, auth, ADMIN_EMAIL)
    r = client.put(f"/api/admin/usuarios/{administrador}", json={"email": ADMIN_EMAIL, "nivel": 2}, headers=auth)
    assert r.status_code == 409


def test_se_puede_desactivar_un_administrador_si_queda_otro_activo(client, auth):
    # Con dos Administradores, el principal puede desactivar al segundo: siempre queda uno.
    client.post(
        "/api/admin/usuarios",
        json={"email": "admin2@test.local", "password": "contrasena-larga-de-prueba", "nivel": 3},
        headers=auth,
    )
    otro_administrador = _id_por_correo(client, auth, "admin2@test.local")
    assert client.post(f"/api/admin/usuarios/{otro_administrador}/desactivar", headers=auth).status_code == 200


def test_editor_no_puede_gestionar_usuarios(client, editor_auth):
    assert client.get("/api/admin/usuarios", headers=editor_auth).status_code == 403
    assert client.post("/api/admin/usuarios", json=NUEVO, headers=editor_auth).status_code == 403


def test_gestion_de_usuarios_sin_sesion_rechazada(client):
    assert client.get("/api/admin/usuarios").status_code == 401
    assert client.post("/api/admin/usuarios", json=NUEVO).status_code == 401
