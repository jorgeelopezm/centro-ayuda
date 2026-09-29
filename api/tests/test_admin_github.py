"""Enlace de GitHub por portal (solo Administrador).

Espejo de `test_admin_plantilla.py`: escritura reservada al Administrador, URL validada
en el servidor (solo `https://github.com/…`, 422 en otro caso) y publicación del valor
guardado en el contenido público. Sin enlace, la clave no viaja (`exclude_none`).
"""

from __future__ import annotations

import pytest

URL = "https://github.com/lupaterra/documentacion"


def test_administrador_guarda_el_enlace_y_se_publica(client, auth):
    r = client.put("/api/admin/ajustes/github", json={"url": URL}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"url": URL}
    for idioma in ("es", "pt"):
        assert client.get(f"/api/{idioma}/contenido").json()["githubUrl"] == URL


def test_sin_enlace_la_clave_no_viaja(client):
    assert "githubUrl" not in client.get("/api/es/contenido").json()


@pytest.mark.parametrize("vacio", ["", "   ", None])
def test_url_vacia_o_nula_borra_el_enlace(client, auth, vacio):
    assert client.put("/api/admin/ajustes/github", json={"url": URL}, headers=auth).status_code == 200
    r = client.put("/api/admin/ajustes/github", json={"url": vacio}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"url": None}
    assert "githubUrl" not in client.get("/api/es/contenido").json()


@pytest.mark.parametrize(
    "invalida",
    [
        "http://github.com/lupaterra",  # sin TLS
        "https://gitlab.com/lupaterra",  # otro host
        "https://github.com.evil.example/x",  # host que solo empieza igual
        "https://usuario@github.com/x",  # credenciales en la URL
        "https://github.com:8443/x",  # puerto explícito
        "javascript:alert(1)",
        "https://github.com/" + "a" * 300,  # supera el máximo
    ],
)
def test_url_que_no_es_de_github_es_422_y_no_persiste(client, auth, invalida):
    assert client.put("/api/admin/ajustes/github", json={"url": URL}, headers=auth).status_code == 200
    r = client.put("/api/admin/ajustes/github", json={"url": invalida}, headers=auth)
    assert r.status_code == 422, r.text
    assert client.get("/api/es/contenido").json()["githubUrl"] == URL


def test_campos_extra_son_422(client, auth):
    cuerpo = {"url": URL, "otra": "cosa"}
    assert client.put("/api/admin/ajustes/github", json=cuerpo, headers=auth).status_code == 422


def test_editor_no_puede_fijar_el_enlace(client, editor_auth):
    r = client.put("/api/admin/ajustes/github", json={"url": URL}, headers=editor_auth)
    assert r.status_code == 403
    assert "githubUrl" not in client.get("/api/es/contenido").json()


def test_anonymous_no_puede_fijar_el_enlace(client):
    assert client.put("/api/admin/ajustes/github", json={"url": URL}).status_code == 401
    assert "githubUrl" not in client.get("/api/es/contenido").json()
