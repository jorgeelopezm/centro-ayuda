"""Tests de los endpoints de supervisión (`api/app/routers/admin_chats.py`).

Cubren las ocho garantías de la tarea 6.6:

(a) Anonymous → 401 en listado y detalle.
(b) Editor del portal A no ve chats del portal B.
(c) SuperAdmin puede leer chats de otro portal con `?portal_id=`.
(d) Detalle de un `chat_id` inexistente → 404.
(e) Detalle de un `chat_id` que pertenece a otro portal → 404 con el mismo
    mensaje (no revela existencia).
(f) Filtros por veredicto (último veredicto del chat) y por rango de fechas
    aplicados al listado.
(g) `metricas` con la base vacía devuelve ceros (no error).
(h) `metricas` con datos usa la caché por proceso en la segunda llamada
    dentro de la ventana de 60 s.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import ChatInteraccion
from app.routers.admin_chats import reset_cache_metricas_para_tests
from app.servicios import PORTAL_DEFECTO_UUID
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    EDITOR_EMAIL,
    EDITOR_PASSWORD,
    SEGUNDO_ADMIN_PASSWORD,
    SEGUNDO_PORTAL_HOST,
    SEGUNDO_PORTAL_UUID,
    SUPERADMIN_EMAIL,
    SUPERADMIN_PASSWORD,
    sembrar_plataforma,
    sembrar_portal_secundario,
)

# El id ya no es un slug legible ("default"): es un UUID (migración
# `0012_portal_uuid`), así que hace falta la constante real del seed.
PORTAL_A = PORTAL_DEFECTO_UUID


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_cache_metricas():
    """La caché del endpoint de métricas vive por proceso: aislarla entre tests
    para que un hit de un test previo no adelante la respuesta del siguiente."""
    reset_cache_metricas_para_tests()
    yield
    reset_cache_metricas_para_tests()


@pytest.fixture
def hacer_cliente(db_session):
    """Fábrica de clientes por host que comparten la misma sesión de base.

    Espeja `hacer_cliente` de `test_aislamiento.py`: dos hosts distintos
    apuntan al mismo estado, así se prueba aislamiento sin duplicar seed.
    Siembra tanto el segundo portal como el portal de plataforma (necesario
    para las peticiones SuperAdmin por `admin.localhost`).
    """
    sembrar_portal_secundario(db_session)
    sembrar_plataforma(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield lambda host: TestClient(app, base_url=f"http://{host}")
    app.dependency_overrides.clear()


def _auth(cliente: TestClient, email: str, password: str) -> dict:
    """Cabecera Authorization: Bearer <access_token> tras `POST /auth/login`."""
    r = cliente.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# --- Helpers de seeding -----------------------------------------------------


def _sembrar_interaccion(
    db,
    *,
    portal_id: str,
    chat_id: str,
    turno: int,
    idioma: str = "es",
    veredicto: str = "respondida",
    creado_en: datetime | None = None,
    consulta: str = "cómo hago X",
    mensaje: str = "Se hace así.",
    citas: list | None = None,
    razon_escalamiento: str | None = None,
    latencia_ms: int = 800,
    proveedor: str = "deepseek",
    modelo: str = "deepseek-chat",
) -> ChatInteraccion:
    """Inserta una fila `chat_interaccion` con valores por defecto sensatos.

    Si no se pasa `creado_en`, se fija `now(UTC)` explícito para que dos
    inserciones consecutivas queden ordenadas por el orden de llamada
    (evita depender de la resolución del server default de SQLite).
    """
    if creado_en is None:
        creado_en = datetime.now(timezone.utc)
    fila = ChatInteraccion(
        id=str(uuid.uuid4()),
        portal_id=portal_id,
        chat_id=chat_id,
        turno=turno,
        idioma=idioma,
        consulta=consulta,
        veredicto=veredicto,
        mensaje=mensaje,
        citas=citas or [],
        razon_escalamiento=razon_escalamiento,
        latencia_ms=latencia_ms,
        proveedor=proveedor,
        modelo=modelo,
        creado_en=creado_en,
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


# --- (a) Anonymous → 401 ----------------------------------------------------


def test_anonymous_no_puede_listar_ni_ver_detalle(hacer_cliente):
    a = hacer_cliente("localhost")

    r_lista = a.get("/api/admin/chats")
    assert r_lista.status_code == 401

    # El chat_id no existe, pero la respuesta debe ser 401 (autenticación
    # primero), no 404: sin cookie no se filtra por chat_id.
    r_detalle = a.get("/api/admin/chats/algun-id")
    assert r_detalle.status_code == 401


# --- (b) Editor de A no ve chats de B ---------------------------------------


def test_editor_del_portal_A_no_ve_chats_del_portal_B(hacer_cliente, db_session):
    _sembrar_interaccion(db_session, portal_id=PORTAL_A, chat_id="chat-de-a", turno=1)
    _sembrar_interaccion(db_session, portal_id=SEGUNDO_PORTAL_UUID, chat_id="chat-de-b", turno=1)

    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.get("/api/admin/chats", headers=auth_editor)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    ids = [it["chat_id"] for it in cuerpo["items"]]
    assert ids == ["chat-de-a"]
    assert cuerpo["siguiente_cursor"] is None


# --- (c) SuperAdmin con ?portal_id=B ----------------------------------------


def test_superadmin_puede_ver_chats_de_otro_portal_con_portal_id(hacer_cliente, db_session):
    _sembrar_interaccion(db_session, portal_id=SEGUNDO_PORTAL_UUID, chat_id="chat-de-b", turno=1)

    # SuperAdmin entra por el host del portal de plataforma.
    sa = hacer_cliente("admin.localhost")
    auth_sa = _auth(sa, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD)

    # Sin `?portal_id=`, el portal efectivo es el de plataforma (vacío).
    r_vacio = sa.get("/api/admin/chats", headers=auth_sa)
    assert r_vacio.status_code == 200
    assert r_vacio.json()["items"] == []

    # Con `?portal_id=B` sí ve el chat del portal B.
    r = sa.get(f"/api/admin/chats?portal_id={SEGUNDO_PORTAL_UUID}", headers=auth_sa)
    assert r.status_code == 200, r.text
    ids = [it["chat_id"] for it in r.json()["items"]]
    assert ids == ["chat-de-b"]


def test_editor_ignora_portal_id_de_otro_portal(hacer_cliente, db_session):
    """Un Editor NO puede sobreescribir el portal por query: el parámetro se
    ignora y se filtra por el portal del host."""
    _sembrar_interaccion(db_session, portal_id=SEGUNDO_PORTAL_UUID, chat_id="chat-de-b", turno=1)
    _sembrar_interaccion(db_session, portal_id=PORTAL_A, chat_id="chat-de-a", turno=1)

    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.get(f"/api/admin/chats?portal_id={SEGUNDO_PORTAL_UUID}", headers=auth_editor)
    assert r.status_code == 200
    ids = [it["chat_id"] for it in r.json()["items"]]
    assert ids == ["chat-de-a"]  # sigue viendo solo su portal


# --- (d) Detalle inexistente → 404 ------------------------------------------


def test_detalle_inexistente_devuelve_404(hacer_cliente):
    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.get("/api/admin/chats/no-existe", headers=auth_editor)
    assert r.status_code == 404


# --- (e) Detalle de otro portal → 404 (mismo mensaje) -----------------------


def test_detalle_de_chat_de_otro_portal_devuelve_404_mismo_mensaje(
    hacer_cliente, db_session,
):
    """Un chat existente pero de otro portal responde 404 con el mismo
    mensaje que un `chat_id` inexistente: no revela existencia."""
    _sembrar_interaccion(
        db_session, portal_id=SEGUNDO_PORTAL_UUID, chat_id="chat-de-b", turno=1,
    )
    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r_de_otro = a.get("/api/admin/chats/chat-de-b", headers=auth_editor)
    r_inexistente = a.get("/api/admin/chats/tampoco-existe", headers=auth_editor)

    assert r_de_otro.status_code == 404
    assert r_inexistente.status_code == 404
    # El mensaje coincide: no hay oráculo cross-tenant.
    assert r_de_otro.json() == r_inexistente.json()


def test_detalle_del_propio_portal_devuelve_hilo_por_turno(hacer_cliente, db_session):
    """Sanidad: un chat del portal del host se sirve completo, ordenado por turno."""
    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c1", turno=1,
        consulta="q1", mensaje="a1", veredicto="respondida",
    )
    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c1", turno=2,
        consulta="q2", mensaje="a2", veredicto="respondida",
    )

    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.get("/api/admin/chats/c1", headers=auth_editor)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["chat_id"] == "c1"
    # El esquema de salida serializa `portal_id` como texto.
    assert cuerpo["portal_id"] == str(PORTAL_A)
    assert [it["turno"] for it in cuerpo["interacciones"]] == [1, 2]
    assert [it["consulta"] for it in cuerpo["interacciones"]] == ["q1", "q2"]


# --- (f) Filtros por veredicto y por rango ----------------------------------


def test_filtro_por_veredicto_y_por_rango_de_fechas(hacer_cliente, db_session):
    ahora = datetime.now(timezone.utc)
    hace_dos_dias = ahora - timedelta(days=2)
    hace_diez_dias = ahora - timedelta(days=10)

    # Tres chats con distintos últimos veredictos.
    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c-respondida", turno=1,
        veredicto="respondida", creado_en=hace_dos_dias,
    )
    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c-escalar", turno=1,
        veredicto="escalar", creado_en=hace_dos_dias,
    )
    # Un chat con dos turnos: el último veredicto es el que gana en el filtro.
    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c-cambia", turno=1,
        veredicto="respondida", creado_en=hace_diez_dias,
    )
    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c-cambia", turno=2,
        veredicto="escalar", creado_en=hace_diez_dias + timedelta(seconds=1),
    )

    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    # Filtro por veredicto=escalar: `c-escalar` y `c-cambia` (que cerró escalado).
    r_esc = a.get("/api/admin/chats?veredicto=escalar", headers=auth_editor)
    assert r_esc.status_code == 200, r_esc.text
    ids_esc = sorted(it["chat_id"] for it in r_esc.json()["items"])
    assert ids_esc == ["c-cambia", "c-escalar"]

    # Filtro por rango de fechas: los últimos 5 días excluye a `c-cambia`.
    # Se pasa por `params=` para que el `+` del offset UTC se URL-encodee bien
    # (interpolarlo en la URL literal lo convertiría en espacio → 422).
    desde = (ahora - timedelta(days=5)).isoformat()
    r_rango = a.get(
        "/api/admin/chats", params={"desde": desde}, headers=auth_editor,
    )
    assert r_rango.status_code == 200, r_rango.text
    ids_rango = sorted(it["chat_id"] for it in r_rango.json()["items"])
    assert ids_rango == ["c-escalar", "c-respondida"]


# --- (g) Métricas sin datos → ceros -----------------------------------------


def test_metricas_sin_datos_devuelve_ceros(hacer_cliente):
    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    r = a.get("/api/admin/chats/metricas", headers=auth_editor)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["chats_total"] == 0
    assert cuerpo["chats_respondidos_con_cita_pct"] == 0.0
    assert cuerpo["chats_escalados"] == 0
    # El rango efectivo viaja en la respuesta.
    assert cuerpo["desde"] and cuerpo["hasta"]


# --- (h) Métricas usan caché por proceso ------------------------------------


def test_metricas_usa_cache_en_segunda_llamada_dentro_de_la_ventana(
    hacer_cliente, db_session,
):
    """La primera llamada calcula y guarda; la segunda debe leer del caché
    aunque cambie el estado subyacente (se comprueba insertando entre las
    dos llamadas y viendo que el número no cambia)."""
    ahora = datetime.now(timezone.utc)

    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c1", turno=1,
        veredicto="respondida", creado_en=ahora - timedelta(hours=1),
    )

    a = hacer_cliente("localhost")
    auth_editor = _auth(a, EDITOR_EMAIL, EDITOR_PASSWORD)

    # Fijamos rango explícito para que la clave del caché sea idéntica en
    # ambas llamadas (con default, cada llamada usaría un `hasta=now()`
    # ligeramente distinto y no habría hit). Pasamos por `params=` porque el
    # `+00:00` del offset UTC no puede ir literal en la URL (el `+` se
    # decodifica como espacio en el servidor → 422).
    params = {
        "desde": (ahora - timedelta(days=1)).isoformat(),
        "hasta": (ahora + timedelta(minutes=1)).isoformat(),
    }

    r1 = a.get("/api/admin/chats/metricas", params=params, headers=auth_editor)
    assert r1.status_code == 200, r1.text
    assert r1.json()["chats_total"] == 1

    # Añadimos un chat más DESPUÉS de calcular la primera respuesta.
    _sembrar_interaccion(
        db_session, portal_id=PORTAL_A, chat_id="c2", turno=1,
        veredicto="escalar", creado_en=ahora,
    )

    # La segunda llamada, dentro del TTL, sigue devolviendo el número cacheado.
    r2 = a.get("/api/admin/chats/metricas", params=params, headers=auth_editor)
    assert r2.status_code == 200
    assert r2.json() == r1.json()  # servido del caché

    # Y al invalidar la caché a mano, sí ve el nuevo chat.
    reset_cache_metricas_para_tests()
    r3 = a.get("/api/admin/chats/metricas", params=params, headers=auth_editor)
    assert r3.status_code == 200
    assert r3.json()["chats_total"] == 2
