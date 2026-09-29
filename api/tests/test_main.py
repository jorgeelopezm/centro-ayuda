"""Punto de entrada: salud, montaje de routers y esquema OpenAPI."""

from __future__ import annotations


def test_salud_responde_ok(client):
    r = client.get("/api/salud")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok"}


def test_la_salud_no_exige_sesion(client):
    # Es el endpoint que mira el arranque/monitorización: nunca detrás del token.
    assert client.get("/api/salud").status_code == 200


def test_ruta_inexistente_es_404(client):
    assert client.get("/api/no-existe").status_code == 404


def test_los_cuatro_routers_estan_montados(client):
    rutas = set(client.get("/openapi.json").json()["paths"])

    assert "/api/{idioma}/contenido" in rutas
    assert "/api/auth/login" in rutas
    assert "/api/admin/articulos" in rutas
    assert "/api/admin/preguntas-sin-resolver" in rutas


def test_el_esquema_openapi_se_genera(client):
    """Smoke test: un esquema Pydantic inválido reventaría aquí, no en producción."""
    r = client.get("/openapi.json")
    assert r.status_code == 200

    esquema = r.json()
    assert esquema["info"]["title"] == "Centro de Ayuda API"
    assert "/api/{idioma}/contenido" in esquema["paths"]


def test_todas_las_rutas_de_admin_declaran_seguridad(client):
    """Ninguna ruta bajo /api/admin puede quedar abierta por olvido.

    La dependencia va en el router, no en cada función: si alguien añade un
    endpoint a otro router con prefijo /api/admin, este test lo caza.
    """
    paths = client.get("/openapi.json").json()["paths"]

    for ruta, operaciones in paths.items():
        if not ruta.startswith("/api/admin"):
            continue
        for metodo, operacion in operaciones.items():
            assert operacion.get("security"), f"{metodo.upper()} {ruta} sin seguridad declarada"
