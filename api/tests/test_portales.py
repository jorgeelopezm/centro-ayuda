"""Resolución del portal a partir del host: troceo puro del host y búsqueda en la base.

Fija la lógica de `app.portales`: normalización del host, extracción del slug de
subdominio (funciones puras) y la resolución completa contra la tabla `dominios` y los
slugs de portal, incluyendo el rechazo de slugs reservados y de hosts desconocidos.
"""

from __future__ import annotations

import pytest

from app.portales import (
    SLUGS_RESERVADOS,
    extraer_subdominio,
    normalizar_host,
    resolver_portal,
)
from app.servicios import PORTAL_DEFECTO_UUID

BASE = "tuapp.com"


# --- Normalización del host (pura) -------------------------------------------

@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Ejemplo.com", "ejemplo.com"),
        ("EJEMPLO.com:8000", "ejemplo.com"),
        ("  localhost:3000  ", "localhost"),
        ("cliente1.tuapp.com", "cliente1.tuapp.com"),
        (None, ""),
        ("", ""),
    ],
)
def test_normalizar_host(entrada, esperado):
    assert normalizar_host(entrada) == esperado


# --- Extracción del subdominio (pura) ----------------------------------------

def test_subdominio_de_un_nivel_devuelve_el_slug():
    assert extraer_subdominio("cliente1.tuapp.com", BASE) == "cliente1"
    # El puerto y las mayúsculas no estorban (se normaliza dentro).
    assert extraer_subdominio("Cliente1.TUAPP.com:443", BASE) == "cliente1"


def test_el_dominio_base_a_secas_no_es_subdominio():
    assert extraer_subdominio("tuapp.com", BASE) is None


def test_subdominio_de_varios_niveles_no_resuelve():
    # Solo se admite un nivel de subdominio como slug de portal.
    assert extraer_subdominio("a.b.tuapp.com", BASE) is None


def test_host_ajeno_al_dominio_base_no_es_subdominio():
    assert extraer_subdominio("ayuda.cliente.com", BASE) is None
    assert extraer_subdominio("localhost", BASE) is None


# --- Resolución completa (con base de datos) ---------------------------------

def test_host_exacto_en_dominios_resuelve(db_session):
    # El seed mínimo mapea `localhost` → portal `default`.
    portal = resolver_portal(db_session, "localhost", base_domain=BASE)
    assert portal is not None
    assert portal.id == PORTAL_DEFECTO_UUID


def test_puerto_y_mayusculas_no_impiden_la_resolucion(db_session):
    portal = resolver_portal(db_session, "LOCALHOST:8000", base_domain=BASE)
    assert portal is not None
    assert portal.id == PORTAL_DEFECTO_UUID


def test_subdominio_resuelve_por_slug_del_portal(db_session):
    # El portal `default` tiene slug `default`: `default.tuapp.com` lo resuelve por slug.
    portal = resolver_portal(db_session, "default.tuapp.com", base_domain=BASE)
    assert portal is not None
    assert portal.id == PORTAL_DEFECTO_UUID


def test_host_desconocido_no_resuelve(db_session):
    # Ni dominio mapeado ni slug de portal: None (el llamador responde 404, sin caer
    # nunca a un portal por defecto arbitrario).
    assert resolver_portal(db_session, "desconocido.example", base_domain=BASE) is None
    assert resolver_portal(db_session, "nadie.tuapp.com", base_domain=BASE) is None


def test_slug_reservado_no_resuelve_a_portal(db_session):
    # Aunque tuviera forma de subdominio, un slug reservado nunca es un portal.
    assert "www" in SLUGS_RESERVADOS
    assert resolver_portal(db_session, "www.tuapp.com", base_domain=BASE) is None
    assert resolver_portal(db_session, "api.tuapp.com", base_domain=BASE) is None


def test_host_vacio_no_resuelve(db_session):
    assert resolver_portal(db_session, "", base_domain=BASE) is None
    assert resolver_portal(db_session, None, base_domain=BASE) is None
