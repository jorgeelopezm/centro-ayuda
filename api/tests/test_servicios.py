"""Ensamblado del contenido, a nivel de servicio.

Cubre las ramas que la API no puede provocar por sí sola: el CRUD exige siempre
los dos idiomas, así que un artículo o una categoría a medio traducir solo puede
llegar a la base por el seed o por una migración. El servicio debe omitirlo en el
idioma que falta en lugar de romper la respuesta del idioma que sí está.

Todo el contenido de estas pruebas vive bajo el portal `default` (`P`): `ensamblar_contenido`
filtra por portal, así que las entidades que se insertan a mano llevan su `portal_id`.
"""

from __future__ import annotations

from datetime import date

from app.models import (
    Articulo,
    ArticuloRelacionado,
    ArticuloTraduccion,
    Categoria,
    CategoriaTraduccion,
    Conversacion,
    Metrica,
)
from app.servicios import PORTAL_DEFECTO_UUID, ensamblar_contenido

# Portal bajo el que se ensambla en estas pruebas (el que siembra `conftest`).
P = PORTAL_DEFECTO_UUID


def _traduccion_articulo(articulo_id: str, idioma: str) -> ArticuloTraduccion:
    return ArticuloTraduccion(
        idioma=idioma,
        portal_id=P,
        slug=f"{articulo_id}-{idioma}",
        titulo=f"Título {idioma}",
        parrafos=["Un párrafo."],
        how_to={"titulo": "Pasos", "pasos": []},
        nota=None,
        faq=[],
    )


def _articulo(db, articulo_id: str, *, orden: int = 0, idiomas=("es", "pt")) -> Articulo:
    a = Articulo(
        id=articulo_id,
        portal_id=P,
        categoria_id="cuenta",
        actualizado=date(2026, 7, 25),
        minutos_lectura=3,
        destacado=False,
        orden=orden,
    )
    for idioma in idiomas:
        a.traducciones.append(_traduccion_articulo(articulo_id, idioma))
    db.add(a)
    db.commit()
    return a


def _categoria(db, categoria_id: str, *, orden: int = 0, idiomas=("es", "pt")) -> None:
    db.add(Categoria(id=categoria_id, portal_id=P, icono="usuario", orden=orden))
    for idioma in idiomas:
        db.add(
            CategoriaTraduccion(
                categoria_id=categoria_id,
                portal_id=P,
                idioma=idioma,
                slug=f"{categoria_id}-{idioma}",
                nombre=f"Nombre {idioma}",
            )
        )
    db.commit()


def _ids(bloque: list[dict]) -> list[str]:
    return [x["id"] for x in bloque]


# --- Traducciones incompletas -----------------------------------------------

def test_categoria_sin_traduccion_se_omite_solo_en_ese_idioma(db_session):
    _categoria(db_session, "facturacion", orden=1, idiomas=("es",))

    assert "facturacion" in _ids(ensamblar_contenido(db_session, "es", P)["categorias"])
    assert "facturacion" not in _ids(ensamblar_contenido(db_session, "pt", P)["categorias"])


def test_la_categoria_a_medias_no_arrastra_a_las_completas(db_session):
    _categoria(db_session, "facturacion", orden=1, idiomas=("es",))

    # "cuenta" viene del seed con los dos idiomas: debe seguir saliendo en pt.
    assert "cuenta" in _ids(ensamblar_contenido(db_session, "pt", P)["categorias"])


def test_articulo_sin_traduccion_se_omite_solo_en_ese_idioma(db_session):
    _articulo(db_session, "solo-en-espanol", idiomas=("es",))
    _articulo(db_session, "bilingue", orden=1)

    assert _ids(ensamblar_contenido(db_session, "es", P)["articulos"]) == [
        "solo-en-espanol",
        "bilingue",
    ]
    assert _ids(ensamblar_contenido(db_session, "pt", P)["articulos"]) == ["bilingue"]


def test_el_articulo_a_medias_tampoco_sale_por_la_api_publica(client, db_session):
    _articulo(db_session, "solo-en-espanol", idiomas=("es",))

    assert client.get("/api/pt/contenido").json()["articulos"] == []
    assert len(client.get("/api/es/contenido").json()["articulos"]) == 1


# --- Ausencias que no deben romper la respuesta ------------------------------

def test_conversacion_ausente_devuelve_lista_vacia(db_session):
    # Clave compuesta `(portal_id, idioma)`: la conversación se pide por ambas.
    db_session.delete(db_session.get(Conversacion, (P, "pt")))
    db_session.commit()

    contenido = ensamblar_contenido(db_session, "pt", P)
    assert contenido["conversacion"] == []
    # El resto del idioma sigue en pie: la ausencia no vacía el contenido entero.
    assert contenido["categorias"] != []


def test_base_sin_metricas_devuelve_lista_vacia(db_session):
    for m in db_session.query(Metrica).all():
        db_session.delete(m)
    db_session.commit()

    assert ensamblar_contenido(db_session, "es", P)["metricas"] == []


def test_idioma_sin_nada_devuelve_los_cuatro_bloques_vacios(db_session):
    """`fr` no existe en la base: el servicio devuelve la forma completa, vacía.

    El router lo corta antes con un 404; esto fija que el servicio no explota
    si alguna vez se le pasa un idioma sin datos.
    """
    contenido = ensamblar_contenido(db_session, "fr", P)

    assert set(contenido) == {
        "empresa",
        "acento",
        "bannerDesde",
        "bannerMedio",
        "bannerHasta",
        "plantilla",
        "githubUrl",
        "logo",
        "logoVersion",
        "categorias",
        "articulos",
        "conversacion",
        "metricas",
    }
    # `empresa` y la marca son del portal (no dependen del idioma): salen con su valor
    # aunque no haya contenido de ese idioma.
    assert contenido == {
        "empresa": "Acme",
        "acento": "#4338ca",
        "bannerDesde": "#3730a3",
        "bannerMedio": "#4338ca",
        "bannerHasta": "#4f46e5",
        "plantilla": "default",
        "githubUrl": None,
        "logo": False,
        "logoVersion": None,
        "categorias": [],
        "articulos": [],
        "conversacion": [],
        "metricas": [],
    }


# --- Ordenación --------------------------------------------------------------

def test_las_categorias_salen_por_su_campo_orden(db_session):
    # Se insertan al revés de como deben salir.
    _categoria(db_session, "ultima", orden=9)
    _categoria(db_session, "primera", orden=-1)

    # "cuenta" viene del seed con orden 0, entre las dos.
    assert _ids(ensamblar_contenido(db_session, "es", P)["categorias"]) == [
        "primera",
        "cuenta",
        "ultima",
    ]


def test_los_articulos_salen_por_su_campo_orden(db_session):
    _articulo(db_session, "tercero", orden=3)
    _articulo(db_session, "primero", orden=1)
    _articulo(db_session, "segundo", orden=2)

    assert _ids(ensamblar_contenido(db_session, "es", P)["articulos"]) == [
        "primero",
        "segundo",
        "tercero",
    ]


def test_las_metricas_salen_por_su_campo_orden(db_session):
    db_session.add(Metrica(portal_id=P, idioma="es", clave="resueltas", valor="120", orden=-1))
    db_session.commit()

    claves = [m["clave"] for m in ensamblar_contenido(db_session, "es", P)["metricas"]]
    assert claves == ["resueltas", "sinResolver"]


def test_las_metricas_de_un_idioma_no_se_mezclan_con_las_del_otro(db_session):
    db_session.add(Metrica(portal_id=P, idioma="pt", clave="soloPt", valor="7", orden=1))
    db_session.commit()

    assert [m["clave"] for m in ensamblar_contenido(db_session, "es", P)["metricas"]] == ["sinResolver"]
    assert [m["clave"] for m in ensamblar_contenido(db_session, "pt", P)["metricas"]] == [
        "sinResolver",
        "soloPt",
    ]


def test_los_relacionados_salen_por_orden_y_no_por_insercion(db_session):
    # Los relacionados deben existir (integridad referencial): se crean primero,
    # con un `orden` posterior para que `con-relacionados` siga siendo el primero.
    _articulo(db_session, "primero", orden=1)
    _articulo(db_session, "segundo", orden=2)
    _articulo(db_session, "tercero", orden=3)

    a = _articulo(db_session, "con-relacionados", orden=0)
    # Se insertan desordenados a propósito: manda `orden`, no el orden de alta.
    a.relacionados.append(ArticuloRelacionado(relacionado_id="tercero", orden=2))
    a.relacionados.append(ArticuloRelacionado(relacionado_id="primero", orden=0))
    a.relacionados.append(ArticuloRelacionado(relacionado_id="segundo", orden=1))
    db_session.commit()
    db_session.expire_all()

    articulo = ensamblar_contenido(db_session, "es", P)["articulos"][0]
    assert articulo["id"] == "con-relacionados"
    assert articulo["relacionados"] == ["primero", "segundo", "tercero"]


# --- Forma de la salida ------------------------------------------------------

def test_la_fecha_del_articulo_sale_en_iso(db_session):
    _articulo(db_session, "con-fecha")

    assert ensamblar_contenido(db_session, "es", P)["articulos"][0]["actualizado"] == "2026-07-25"


def test_el_id_de_categoria_del_articulo_es_el_estable_no_el_slug(db_session):
    """El artículo referencia la categoría por id, igual en es y pt."""
    _articulo(db_session, "con-categoria")

    es = ensamblar_contenido(db_session, "es", P)["articulos"][0]
    pt = ensamblar_contenido(db_session, "pt", P)["articulos"][0]
    assert es["categoria"] == pt["categoria"] == "cuenta"
