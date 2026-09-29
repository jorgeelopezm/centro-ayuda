"""Ajuste de plantilla del centro de ayuda por portal (solo Administrador).

Espejo de `test_admin_marca.py` para el ajuste nuevo: escritura reservada al nivel
Administrador, valor validado en el servidor (422) y publicación del valor guardado en
el contenido público. El 401 de Anonymous y el 403 de Editor son la semántica de sesión
documentada en `app/deps.py`: 401 = sin sesión válida, 403 = sesión sin nivel suficiente.
"""

from __future__ import annotations

# Escritura: ambos valores admitidos, respuesta con el valor guardado --------------

def test_administrador_guarda_documentacion(client, auth):
    r = client.put("/api/admin/ajustes/plantilla", json={"plantilla": "documentacion"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"plantilla": "documentacion"}


def test_administrador_vuelve_a_default(client, auth):
    assert client.put(
        "/api/admin/ajustes/plantilla", json={"plantilla": "documentacion"}, headers=auth
    ).status_code == 200
    r = client.put("/api/admin/ajustes/plantilla", json={"plantilla": "default"}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json() == {"plantilla": "default"}


# Lectura pública: el valor guardado viaja en el contenido de los dos idiomas -----

def test_la_plantilla_guardada_se_publica_en_el_contenido(client, auth):
    assert client.put(
        "/api/admin/ajustes/plantilla", json={"plantilla": "documentacion"}, headers=auth
    ).status_code == 200
    for idioma in ("es", "pt"):
        assert client.get(f"/api/{idioma}/contenido").json()["plantilla"] == "documentacion"


def test_un_portal_recien_sembrado_publica_la_predeterminada(client):
    # La fila de ajustes del seed no elige plantilla: se publica `default`.
    assert client.get("/api/es/contenido").json()["plantilla"] == "default"


# Validación: un valor no admitido es 422 y no cambia nada ------------------------

def test_valor_no_admitido_con_sesion_es_422_y_no_persiste(client, auth):
    assert client.put(
        "/api/admin/ajustes/plantilla", json={"plantilla": "documentacion"}, headers=auth
    ).status_code == 200
    r = client.put("/api/admin/ajustes/plantilla", json={"plantilla": "compacta"}, headers=auth)
    assert r.status_code == 422, r.text
    # La plantilla guardada sigue siendo la anterior.
    assert client.get("/api/es/contenido").json()["plantilla"] == "documentacion"


def test_cuerpo_sin_plantilla_es_422(client, auth):
    assert client.put("/api/admin/ajustes/plantilla", json={}, headers=auth).status_code == 422


def test_campos_extra_son_422(client, auth):
    cuerpo = {"plantilla": "default", "otra": "cosa"}
    assert client.put("/api/admin/ajustes/plantilla", json=cuerpo, headers=auth).status_code == 422


# Nivel insuficiente: Editor 403 (sin nivel) y Anonymous 401 (sin sesión) ----------

def test_editor_no_puede_elegir_la_plantilla(client, editor_auth):
    r = client.put("/api/admin/ajustes/plantilla", json={"plantilla": "documentacion"}, headers=editor_auth)
    assert r.status_code == 403
    # No se persistió: la plantilla publicada sigue siendo la predeterminada.
    assert client.get("/api/es/contenido").json()["plantilla"] == "default"


def test_anonymous_no_puede_elegir_la_plantilla(client):
    r = client.put("/api/admin/ajustes/plantilla", json={"plantilla": "documentacion"})
    assert r.status_code == 401
    assert client.get("/api/es/contenido").json()["plantilla"] == "default"
