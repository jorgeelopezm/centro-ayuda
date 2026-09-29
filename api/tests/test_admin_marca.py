"""Marca visual: paleta con validación de contraste, y logotipo (PNG/ICO)."""

from __future__ import annotations

from app.contraste import derivar_degradado_banner

# Binarios mínimos: el detector decide por los primeros bytes (magic bytes).
PNG_VALIDO = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
ICO_VALIDO = b"\x00\x00\x01\x00" + b"\x00" * 32
JPEG_VALIDO = b"\xff\xd8\xff\xe0" + b"\x00" * 32
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

# El Administrador solo elige el acento; el banner se deriva en el servidor.
PALETA_VALIDA = {"acento": "#4338ca"}


# --- Paleta: derivación, contraste y autorización ---------------------------

def test_administrador_guarda_solo_el_acento_y_recibe_el_banner_derivado(client, auth):
    r = client.put("/api/admin/ajustes/marca", json=PALETA_VALIDA, headers=auth)
    assert r.status_code == 200, r.text
    esperado = derivar_degradado_banner("#4338ca")
    cuerpo = r.json()
    assert cuerpo["acento"] == "#4338ca"
    assert cuerpo["bannerDesde"] == esperado["desde"]
    assert cuerpo["bannerMedio"] == esperado["medio"]
    assert cuerpo["bannerHasta"] == esperado["hasta"]


def test_el_banner_se_deriva_del_acento_en_el_contenido_publico(client, auth):
    nueva = {"acento": "#0f766e"}  # teal oscuro, contrasta con blanco
    assert client.put("/api/admin/ajustes/marca", json=nueva, headers=auth).status_code == 200
    contenido = client.get("/api/es/contenido").json()
    esperado = derivar_degradado_banner("#0f766e")
    assert contenido["acento"] == "#0f766e"
    assert contenido["bannerDesde"] == esperado["desde"]
    assert contenido["bannerMedio"] == esperado["medio"]
    assert contenido["bannerHasta"] == esperado["hasta"]


def test_paradas_de_banner_en_el_cuerpo_se_ignoran(client, auth):
    # El cuerpo trae paradas arbitrarias (una casi blanca que no contrastaría); el
    # servidor las descarta y persiste el degradado derivado del acento.
    cuerpo = {
        "acento": "#4338ca",
        "bannerDesde": "#ffffff",
        "bannerMedio": "#fffbe6",
        "bannerHasta": "#fefefe",
    }
    assert client.put("/api/admin/ajustes/marca", json=cuerpo, headers=auth).status_code == 200
    contenido = client.get("/api/es/contenido").json()
    esperado = derivar_degradado_banner("#4338ca")
    assert contenido["bannerDesde"] == esperado["desde"]
    assert contenido["bannerDesde"] != "#ffffff"  # no se coló el blanco del cuerpo


def test_acento_con_contraste_insuficiente_es_422(client, auth):
    malo = {"acento": "#cccccc"}
    r = client.put("/api/admin/ajustes/marca", json=malo, headers=auth)
    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert detalle["ratio"] < detalle["minimo"]
    # No se persistió: el contenido conserva el acento anterior.
    assert client.get("/api/es/contenido").json()["acento"] != "#cccccc"


def test_hex_mal_formado_es_422(client, auth):
    malo = {"acento": "azul"}
    assert client.put("/api/admin/ajustes/marca", json=malo, headers=auth).status_code == 422


def test_editor_no_puede_cambiar_la_paleta(client, editor_auth):
    assert client.put("/api/admin/ajustes/marca", json=PALETA_VALIDA, headers=editor_auth).status_code == 403


def test_anonymous_no_puede_cambiar_la_paleta(client):
    assert client.put("/api/admin/ajustes/marca", json=PALETA_VALIDA).status_code == 401


# --- Logotipo ---------------------------------------------------------------

def test_sin_logo_el_servido_es_404(client):
    assert client.get("/api/marca/logo").status_code == 404


def test_administrador_sube_png_y_se_sirve(client, auth):
    r = client.post("/api/admin/ajustes/logo", content=PNG_VALIDO, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json() == {"presente": True, "mime": "image/png"}

    servido = client.get("/api/marca/logo")
    assert servido.status_code == 200
    assert servido.headers["content-type"] == "image/png"
    assert servido.headers["x-content-type-options"] == "nosniff"
    assert servido.content == PNG_VALIDO


def test_administrador_sube_ico(client, auth):
    r = client.post("/api/admin/ajustes/logo", content=ICO_VALIDO, headers=auth)
    assert r.status_code == 201
    assert r.json()["mime"] == "image/x-icon"


def test_administrador_sube_jpeg_y_se_sirve(client, auth):
    r = client.post("/api/admin/ajustes/logo", content=JPEG_VALIDO, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json() == {"presente": True, "mime": "image/jpeg"}

    servido = client.get("/api/marca/logo")
    assert servido.status_code == 200
    assert servido.headers["content-type"] == "image/jpeg"
    assert servido.content == JPEG_VALIDO


def test_se_rechaza_svg(client, auth):
    assert client.post("/api/admin/ajustes/logo", content=SVG, headers=auth).status_code == 422
    # No se guardó nada.
    assert client.get("/api/marca/logo").status_code == 404


def test_se_rechaza_contenido_que_no_es_png_ni_ico(client, auth):
    # Bytes que declaran ser PNG por Content-Type pero no lo son: mandan los magic bytes.
    cabeceras = {**auth, "Content-Type": "image/png"}
    assert client.post("/api/admin/ajustes/logo", content=b"esto no es una imagen", headers=cabeceras).status_code == 422


def test_se_acepta_png_aunque_el_content_type_mienta(client, auth):
    # El tipo lo decide el contenido, no el Content-Type: PNG real con tipo text/plain.
    cabeceras = {**auth, "Content-Type": "text/plain"}
    assert client.post("/api/admin/ajustes/logo", content=PNG_VALIDO, headers=cabeceras).status_code == 201


def test_se_rechaza_archivo_vacio(client, auth):
    assert client.post("/api/admin/ajustes/logo", content=b"", headers=auth).status_code == 422


def test_editor_no_puede_subir_logo(client, editor_auth):
    assert client.post("/api/admin/ajustes/logo", content=PNG_VALIDO, headers=editor_auth).status_code == 403


def test_anonymous_no_puede_subir_logo(client):
    assert client.post("/api/admin/ajustes/logo", content=PNG_VALIDO).status_code == 401
