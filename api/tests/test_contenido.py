"""API pública de contenido."""

from __future__ import annotations

from datetime import date

from tests.conftest import articulo_valido


def test_contenido_idioma_admitido(client):
    r = client.get("/api/es/contenido")
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"empresa", "acento", "bannerDesde", "bannerMedio", "bannerHasta", "plantilla", "logo", "categorias", "articulos", "conversacion", "metricas"}
    assert cuerpo["categorias"][0]["id"] == "cuenta"


def test_contenido_idioma_no_admitido(client):
    r = client.get("/api/fr/contenido")
    assert r.status_code == 404


def test_articulo_creado_aparece_en_contenido(client, auth):
    assert client.post("/api/admin/articulos", json=articulo_valido(), headers=auth).status_code == 201

    r = client.get("/api/es/contenido")
    ids = [a["id"] for a in r.json()["articulos"]]
    assert "nuevo-articulo" in ids


def test_portugues_tiene_la_misma_forma_que_espanol(client):
    r = client.get("/api/pt/contenido")
    assert r.status_code == 200
    assert set(r.json()) == {"empresa", "acento", "bannerDesde", "bannerMedio", "bannerHasta", "plantilla", "logo", "categorias", "articulos", "conversacion", "metricas"}


def test_el_contenido_publico_incluye_el_campo_empresa(client):
    # El nombre de marca ([Empresa]) lo ve cualquier visitante anónimo.
    for idioma in ("es", "pt"):
        assert client.get(f"/api/{idioma}/contenido").json()["empresa"] == "Acme"


def test_la_categoria_se_traduce_manteniendo_el_id(client):
    es = client.get("/api/es/contenido").json()["categorias"][0]
    pt = client.get("/api/pt/contenido").json()["categorias"][0]

    # El id es estable entre idiomas; slug y nombre son propios de cada uno.
    assert es["id"] == pt["id"] == "cuenta"
    assert es["slug"] == "cuenta" and pt["slug"] == "conta"
    assert es["nombre"] == "Cuenta" and pt["nombre"] == "Conta"
    # El icono es presentación, no depende del idioma; ya no lleva color propio
    # (se deriva del acento del portal).
    assert es["icono"] == pt["icono"]
    assert "fondo" not in es and "fondo" not in pt
    assert "texto" not in es and "texto" not in pt


def test_el_articulo_sale_con_el_slug_de_cada_idioma(client, auth):
    client.post("/api/admin/articulos", json=articulo_valido(), headers=auth)

    es = client.get("/api/es/contenido").json()["articulos"][0]
    pt = client.get("/api/pt/contenido").json()["articulos"][0]

    assert es["id"] == pt["id"] == "nuevo-articulo"
    assert es["slug"] == "nuevo-articulo"
    assert pt["slug"] == "novo-artigo"
    assert es["titulo"] == "Nuevo artículo"
    assert pt["titulo"] == "Novo artigo"


def test_el_articulo_cumple_el_contrato_de_types_ts(client, auth):
    client.post("/api/admin/articulos", json=articulo_valido(), headers=auth)
    articulo = client.get("/api/es/contenido").json()["articulos"][0]

    assert set(articulo) == {
        "id", "slug", "titulo", "categoria", "actualizado", "minutosLectura",
        "destacado", "parrafos", "howTo", "faq", "relacionados",
    }
    # La fecha la sella el servidor a hoy en cada guardado (ya no se confía en el
    # valor enviado por el cliente, aquí "2026-07-25").
    assert articulo["actualizado"] == date.today().isoformat()
    assert articulo["minutosLectura"] == 2
    assert articulo["destacado"] is True


def test_la_nota_nula_se_omite_en_vez_de_ir_como_null(client, auth):
    client.post("/api/admin/articulos", json=articulo_valido(), headers=auth)
    articulo = client.get("/api/es/contenido").json()["articulos"][0]

    # `nota` es opcional en types.ts: si no hay, la clave no viaja.
    assert "nota" not in articulo


def test_la_nota_con_texto_si_viaja(client, auth):
    payload = articulo_valido()
    payload["es"]["nota"] = "Ojo con esto."
    client.post("/api/admin/articulos", json=payload, headers=auth)

    articulo = client.get("/api/es/contenido").json()["articulos"][0]
    assert articulo["nota"] == "Ojo con esto."


def test_el_contenido_publico_no_expone_las_preguntas_sin_resolver(client):
    """Regresión: el texto que escriben las personas usuarias no sale sin autenticar.

    La base sembrada tiene una pregunta; el endpoint público no debe mencionarla
    ni por clave ni por contenido. Solo se sirve en /api/admin/preguntas-sin-resolver.
    """
    for idioma in ("es", "pt"):
        r = client.get(f"/api/{idioma}/contenido")
        assert r.status_code == 200
        assert "preguntasSinResolver" not in r.json()
        assert "contraseña" not in r.text


def test_las_preguntas_sin_resolver_siguen_disponibles_para_el_panel(client, auth):
    # El dato no desaparece: cambia de puerta, y esa puerta exige sesión.
    filas = client.get("/api/admin/preguntas-sin-resolver?idioma=es", headers=auth).json()
    assert len(filas) == 1
    assert filas[0]["pregunta"] == "¿Cómo cambio mi contraseña?"


def test_metricas_y_conversacion_son_las_del_idioma(client):
    es = client.get("/api/es/contenido").json()
    pt = client.get("/api/pt/contenido").json()

    assert es["metricas"] == [{"clave": "sinResolver", "valor": "34"}]
    assert pt["metricas"] == [{"clave": "sinResolver", "valor": "34"}]
    assert es["conversacion"] == [{"autor": "usuario", "texto": "hola"}]
    assert pt["conversacion"] == [{"autor": "usuario", "texto": "hola"}]


def test_el_articulo_eliminado_desaparece_del_contenido(client, auth):
    client.post("/api/admin/articulos", json=articulo_valido(), headers=auth)
    assert client.get("/api/es/contenido").json()["articulos"] != []

    client.delete("/api/admin/articulos/nuevo-articulo", headers=auth)
    assert client.get("/api/es/contenido").json()["articulos"] == []
