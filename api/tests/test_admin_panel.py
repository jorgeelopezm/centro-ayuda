"""Panel interno: listado de preguntas sin resolver y cierre del ciclo KCS."""

from __future__ import annotations

from datetime import date

from app.models import PreguntaSinResolver
from app.servicios import PORTAL_DEFECTO_UUID
from tests.conftest import articulo_valido

RUTA = "/api/admin/preguntas-sin-resolver"


def _pregunta(db, texto: str, *, idioma: str = "pt", orden: int = 0) -> None:
    db.add(
        PreguntaSinResolver(
            portal_id=PORTAL_DEFECTO_UUID,
            idioma=idioma, pregunta=texto, veces=3, similitud=0.4,
            fecha=date(2026, 7, 21), estado="nueva", orden=orden,
        )
    )
    db.commit()


def test_listar_sin_sesion_rechazado(client):
    assert client.get(RUTA).status_code == 401


def test_listar_devuelve_la_forma_que_espera_el_panel(client, auth):
    filas = client.get(RUTA, headers=auth).json()
    assert len(filas) == 1
    assert set(filas[0]) == {"id", "idioma", "pregunta", "veces", "similitud", "fecha", "estado"}
    assert filas[0]["idioma"] == "es"
    assert filas[0]["fecha"] == "2026-07-20"  # ISO, para el atributo datetime de <time>
    assert filas[0]["estado"] == "nueva"


def test_filtro_por_idioma(client, auth):
    assert len(client.get(f"{RUTA}?idioma=es", headers=auth).json()) == 1
    # El seed mínimo solo tiene pregunta en español.
    assert client.get(f"{RUTA}?idioma=pt", headers=auth).json() == []


def test_sin_filtro_devuelve_todos_los_idiomas(client, auth):
    assert len(client.get(RUTA, headers=auth).json()) == 1


def test_filtro_por_idioma_desconocido_devuelve_vacio(client, auth):
    assert client.get(f"{RUTA}?idioma=fr", headers=auth).json() == []


def test_el_filtro_devuelve_solo_el_idioma_pedido(client, auth, db_session):
    _pregunta(db_session, "Como altero a minha senha?", idioma="pt")

    todas = client.get(RUTA, headers=auth).json()
    assert {p["idioma"] for p in todas} == {"es", "pt"}

    solo_pt = client.get(f"{RUTA}?idioma=pt", headers=auth).json()
    assert [p["idioma"] for p in solo_pt] == ["pt"]


def test_las_preguntas_salen_por_su_campo_orden(client, auth, db_session):
    _pregunta(db_session, "La última", idioma="es", orden=9)
    _pregunta(db_session, "La primera", idioma="es", orden=-1)

    # La sembrada por el fixture tiene orden 0: queda en medio.
    textos = [p["pregunta"] for p in client.get(f"{RUTA}?idioma=es", headers=auth).json()]
    assert textos == ["La primera", "¿Cómo cambio mi contraseña?", "La última"]


def test_la_similitud_viaja_como_numero(client, auth):
    # El panel la formatea como porcentaje: si llegara como texto, rompería.
    assert client.get(RUTA, headers=auth).json()[0]["similitud"] == 0.5


def test_crear_articulo_desde_pregunta_sin_sesion_rechazado(client):
    assert client.post(f"{RUTA}/1/crear-articulo", json=articulo_valido()).status_code == 401


def test_crear_articulo_desde_pregunta_inexistente_es_404(client, auth):
    r = client.post(f"{RUTA}/9999/crear-articulo", json=articulo_valido(), headers=auth)
    assert r.status_code == 404


def test_crear_articulo_desde_pregunta_con_id_duplicado_es_409(client, auth):
    assert client.post("/api/admin/articulos", json=articulo_valido("repetido"), headers=auth).status_code == 201
    pid = client.get(RUTA, headers=auth).json()[0]["id"]

    r = client.post(f"{RUTA}/{pid}/crear-articulo", json=articulo_valido("repetido"), headers=auth)
    assert r.status_code == 409


def test_la_pregunta_sigue_nueva_si_falla_la_creacion(client, auth):
    client.post("/api/admin/articulos", json=articulo_valido("repetido"), headers=auth)
    pid = client.get(RUTA, headers=auth).json()[0]["id"]

    client.post(f"{RUTA}/{pid}/crear-articulo", json=articulo_valido("repetido"), headers=auth)

    # El conflicto aborta antes de tocar el estado: no se cubre una pregunta sin artículo.
    assert client.get(RUTA, headers=auth).json()[0]["estado"] == "nueva"


def test_crear_articulo_desde_pregunta_exige_los_dos_idiomas(client, auth):
    pid = client.get(RUTA, headers=auth).json()[0]["id"]
    payload = articulo_valido("solo-es")
    del payload["pt"]

    assert client.post(f"{RUTA}/{pid}/crear-articulo", json=payload, headers=auth).status_code == 422
    assert client.get(RUTA, headers=auth).json()[0]["estado"] == "nueva"


def test_el_articulo_creado_desde_la_pregunta_queda_disponible(client, auth):
    pid = client.get(RUTA, headers=auth).json()[0]["id"]

    r = client.post(f"{RUTA}/{pid}/crear-articulo", json=articulo_valido("desde-kcs"), headers=auth)
    assert r.status_code == 201

    detalle = client.get("/api/admin/articulos/desde-kcs", headers=auth)
    assert detalle.status_code == 200
    assert detalle.json()["pt"]["titulo"] == "Novo artigo"
