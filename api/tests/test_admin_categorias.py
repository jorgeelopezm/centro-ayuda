"""CRUD de categorías: atomicidad bilingüe, borrado con integridad y autorización."""

from __future__ import annotations

from app.models import Categoria
from tests.conftest import articulo_valido, categoria_valida


# --- Esquema tras la migración `0014_categorias_sin_color` -------------------


def test_categoria_no_tiene_columnas_fondo_ni_texto():
    """Fija la semántica del `upgrade` de la migración `0014_categorias_sin_color`
    a nivel de modelo (los tests construyen el esquema desde `models.py` con
    `Base.metadata.create_all`, no ejecutando Alembic): la tabla `categorias` ya
    no declara `fondo` ni `texto`, y conserva el resto de columnas intactas."""
    columnas = set(Categoria.__table__.columns.keys())
    assert "fondo" not in columnas
    assert "texto" not in columnas
    assert {"id", "portal_id", "icono", "orden"} <= columnas


def test_categoria_sembrada_conserva_sus_demas_campos(client, auth):
    """La categoría sembrada `cuenta` (creada antes de este cambio en el fixture de
    seed) sigue teniendo nombre, slug, icono y orden tras quitar fondo/texto del
    modelo: la migración no debe tocar esas columnas ni las filas existentes."""
    cuerpo = client.get("/api/admin/categorias/cuenta", headers=auth).json()
    assert cuerpo["icono"] == "usuario"
    assert cuerpo["orden"] == 0
    assert cuerpo["es"]["slug"] == "cuenta"
    assert cuerpo["es"]["nombre"] == "Cuenta"
    assert cuerpo["pt"]["slug"] == "conta"
    assert cuerpo["pt"]["nombre"] == "Conta"
    assert "fondo" not in cuerpo
    assert "texto" not in cuerpo


# --- Alta bilingüe ----------------------------------------------------------

def test_crear_bilingue_valido(client, auth):
    r = client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["es"]["nombre"] == "Facturación"
    assert cuerpo["pt"]["nombre"] == "Faturação"
    assert cuerpo["orden"] == 3


def test_crear_con_un_solo_idioma_rechazado(client, auth):
    payload = categoria_valida()
    del payload["pt"]
    assert client.post("/api/admin/categorias", json=payload, headers=auth).status_code == 422


def test_crear_con_nombre_vacio_rechazado(client, auth):
    payload = categoria_valida()
    payload["es"]["nombre"] = ""
    assert client.post("/api/admin/categorias", json=payload, headers=auth).status_code == 422


def test_crear_con_icono_fuera_del_conjunto_cerrado_es_422(client, auth):
    payload = categoria_valida()
    payload["icono"] = "no-existe"
    r = client.post("/api/admin/categorias", json=payload, headers=auth)
    assert r.status_code == 422
    assert client.get("/api/admin/categorias/facturacion", headers=auth).status_code == 404


def test_editar_con_icono_fuera_del_conjunto_cerrado_es_422(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    cambio = categoria_valida()
    del cambio["id"]
    cambio["icono"] = "no-existe"
    r = client.put("/api/admin/categorias/facturacion", json=cambio, headers=auth)
    assert r.status_code == 422
    # No se modificó: el icono sigue siendo el original.
    assert client.get("/api/admin/categorias/facturacion", headers=auth).json()["icono"] == "documento"


def test_crear_con_icono_de_desarrollo(client, auth):
    payload = categoria_valida()
    payload["icono"] = "terminal"
    r = client.post("/api/admin/categorias", json=payload, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["icono"] == "terminal"


def test_crear_sin_icono_y_publicarla_sin_la_clave(client, auth):
    payload = categoria_valida()
    payload["icono"] = None
    r = client.post("/api/admin/categorias", json=payload, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["icono"] is None
    # En el contenido público `exclude_none` omite la clave: el frontend lo lee como
    # «sin icono».
    publica = next(c for c in client.get("/api/es/contenido").json()["categorias"] if c["id"] == "facturacion")
    assert "icono" not in publica


def test_quitar_el_icono_al_editar(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    cambio = categoria_valida()
    del cambio["id"]
    cambio["icono"] = None
    assert client.put("/api/admin/categorias/facturacion", json=cambio, headers=auth).status_code == 200
    assert client.get("/api/admin/categorias/facturacion", headers=auth).json()["icono"] is None


def test_omitir_el_campo_icono_sigue_siendo_422(client, auth):
    # «Sin icono» es un `null` explícito; olvidar el campo no lo borra en silencio.
    payload = categoria_valida()
    del payload["icono"]
    assert client.post("/api/admin/categorias", json=payload, headers=auth).status_code == 422


def test_crear_con_id_duplicado_es_409(client, auth):
    assert client.post("/api/admin/categorias", json=categoria_valida(), headers=auth).status_code == 201
    assert client.post("/api/admin/categorias", json=categoria_valida(), headers=auth).status_code == 409


def test_id_y_slugs_se_normalizan_en_el_servidor(client, auth):
    payload = categoria_valida()
    payload["id"] = "Pagos y Facturación"
    payload["es"]["slug"] = "Facturación Mensual"
    payload["pt"]["slug"] = "Faturação Mensal"
    creado = client.post("/api/admin/categorias", json=payload, headers=auth).json()
    assert creado["id"] == "pagos-y-facturacion"
    assert creado["es"]["slug"] == "facturacion-mensual"
    assert creado["pt"]["slug"] == "faturacao-mensal"
    assert client.get("/api/admin/categorias/pagos-y-facturacion", headers=auth).status_code == 200


# --- Listado y detalle ------------------------------------------------------

def test_listar_incluye_la_sembrada_y_las_creadas(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    ids = {c["id"] for c in client.get("/api/admin/categorias", headers=auth).json()}
    assert {"cuenta", "facturacion"} <= ids


def test_obtener_devuelve_los_dos_idiomas(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    cuerpo = client.get("/api/admin/categorias/facturacion", headers=auth).json()
    assert cuerpo["es"]["slug"] == "facturacion"
    assert cuerpo["pt"]["slug"] == "faturacao"


def test_obtener_inexistente_es_404(client, auth):
    assert client.get("/api/admin/categorias/no-existe", headers=auth).status_code == 404


# --- Edición ----------------------------------------------------------------

def test_editar_reemplaza_las_traducciones(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    cambio = categoria_valida()
    del cambio["id"]
    cambio["es"]["nombre"] = "Pagos"
    cambio["pt"]["nombre"] = "Pagamentos"
    r = client.put("/api/admin/categorias/facturacion", json=cambio, headers=auth)
    assert r.status_code == 200
    assert r.json()["es"]["nombre"] == "Pagos"
    assert r.json()["pt"]["nombre"] == "Pagamentos"


def test_editar_exige_los_dos_idiomas(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    cambio = categoria_valida()
    del cambio["id"]
    del cambio["pt"]
    assert client.put("/api/admin/categorias/facturacion", json=cambio, headers=auth).status_code == 422


def test_editar_rechaza_el_id_en_el_cuerpo(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    cambio = categoria_valida()  # conserva "id"
    assert client.put("/api/admin/categorias/facturacion", json=cambio, headers=auth).status_code == 422


def test_editar_inexistente_es_404(client, auth):
    cambio = categoria_valida()
    del cambio["id"]
    assert client.put("/api/admin/categorias/no-existe", json=cambio, headers=auth).status_code == 404


# --- Borrado con integridad referencial -------------------------------------

def test_borrar_categoria_vacia(client, auth):
    client.post("/api/admin/categorias", json=categoria_valida(), headers=auth)
    assert client.delete("/api/admin/categorias/facturacion", headers=auth).status_code == 204
    assert client.get("/api/admin/categorias/facturacion", headers=auth).status_code == 404


def test_borrar_categoria_con_articulos_es_409(client, auth):
    # `articulo_valido` referencia la categoría sembrada "cuenta".
    client.post("/api/admin/articulos", json=articulo_valido(), headers=auth)
    r = client.delete("/api/admin/categorias/cuenta", headers=auth)
    assert r.status_code == 409
    # No se borró: la categoría sigue existiendo.
    assert client.get("/api/admin/categorias/cuenta", headers=auth).status_code == 200


def test_borrar_inexistente_es_404(client, auth):
    assert client.delete("/api/admin/categorias/no-existe", headers=auth).status_code == 404


# --- Autorización -----------------------------------------------------------

def test_editor_puede_gestionar_categorias(client, editor_auth):
    assert client.post("/api/admin/categorias", json=categoria_valida(), headers=editor_auth).status_code == 201
    assert client.get("/api/admin/categorias", headers=editor_auth).status_code == 200
    assert client.delete("/api/admin/categorias/facturacion", headers=editor_auth).status_code == 204


def test_anonymous_no_alcanza_el_crud(client):
    assert client.get("/api/admin/categorias").status_code == 401
    assert client.post("/api/admin/categorias", json=categoria_valida()).status_code == 401
    assert client.put("/api/admin/categorias/cuenta", json=categoria_valida()).status_code == 401
    assert client.delete("/api/admin/categorias/cuenta").status_code == 401
