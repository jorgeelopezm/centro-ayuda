"""Fixtures de test: SQLite en memoria, sin Postgres ni migración pgvector."""

from __future__ import annotations

import os

# Configuración de test, fijada ANTES de importar `app.*`: `jwt_secret` y
# `admin_password` ya no tienen valor por defecto, y la variable de entorno tiene
# prioridad sobre el .env. Así los tests no dependen del .env de cada máquina.
# El secreto pasa de 32 bytes: por debajo, PyJWT avisa en cada firma (RFC 7518 §3.2).
os.environ.setdefault("JWT_SECRET", "secreto-de-pruebas-largo-y-sin-ningun-valor-real")
os.environ.setdefault("ADMIN_PASSWORD", "contrasena-solo-para-los-tests")

# Dominio base de los portales: el valor por defecto del código (`tuapp.com`), no el del
# `.env` de cada máquina. Los tests que comprueban el host de un portal recién creado
# (`test_portales_gestion.py`) usan ese valor, y en desarrollo el `.env` trae
# `BASE_DOMAIN=localhost` para que resuelvan los subdominios en el navegador: sin fijarlo
# aquí, la misma suite pasa o falla según el `.env` de quien la corre.
os.environ.setdefault("BASE_DOMAIN", "tuapp.com")

# Clave de cifrado válida (Fernet) para los tests de configuración de IA. Se genera
# al vuelo: no es un secreto real y cada corrida usa una distinta.
from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("CLAVE_CIFRADO_IA", Fernet.generate_key().decode())

import uuid  # noqa: E402
from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: F401,E402  (registra las tablas en Base.metadata)
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    AdminUser,
    Ajustes,
    Categoria,
    CategoriaTraduccion,
    Conversacion,
    Dominio,
    Metrica,
    NivelAcceso,
    Portal,
    PreguntaSinResolver,
)
from app.security import hash_password  # noqa: E402
from app.servicios import (  # noqa: E402
    AJUSTES_ID,
    PORTAL_DEFECTO_HOST,
    PORTAL_DEFECTO_SLUG,
    PORTAL_DEFECTO_UUID,
    PORTAL_PLATAFORMA_HOST_DEV,
    PORTAL_PLATAFORMA_SLUG,
    PORTAL_PLATAFORMA_UUID,
)


def pytest_addoption(parser):
    """Opciones CLI del harness de eval del chat (spec `evaluacion-chat-rag`).

    `--real` activa la ejecución contra el proveedor real de `ConfigIA` en
    lugar de los dobles deterministas. Requiere además la variable de entorno
    `CHAT_EVAL_HABILITADO_REAL=1` para no dispararse por accidente con coste.
    """
    parser.addoption(
        "--real",
        action="store_true",
        default=False,
        help=(
            "Ejecuta el harness de eval del chat contra el proveedor real "
            "(requiere CHAT_EVAL_HABILITADO_REAL=1)."
        ),
    )

# El administrador principal es Administrador (como el que siembra el seed): puede todo.
ADMIN_EMAIL = "admin@test.local"
ADMIN_PASSWORD = "secreto-de-prueba"

# Un segundo usuario, de Nivel 2 (Editor), para las pruebas de autorización.
EDITOR_EMAIL = "editor@test.local"
EDITOR_PASSWORD = "secreto-de-prueba-2"

EMPRESA_INICIAL = "Acme"


def _sembrar_minimo(db) -> None:
    # El portal `default` va primero: todo el contenido y los usuarios lo referencian
    # por `portal_id` (multi-tenant). Un solo portal en los tests salvo que una prueba
    # de aislamiento cree otro.
    db.add(
        Portal(
            id=PORTAL_DEFECTO_UUID,
            slug=PORTAL_DEFECTO_SLUG,
            nombre_empresa=EMPRESA_INICIAL,
            estado="activo",
        )
    )
    db.add(Dominio(host=PORTAL_DEFECTO_HOST, portal_id=PORTAL_DEFECTO_UUID, principal=True))
    db.flush()
    db.add(Categoria(id="cuenta", portal_id=PORTAL_DEFECTO_UUID, icono="usuario", orden=0))
    db.add(CategoriaTraduccion(categoria_id="cuenta", portal_id=PORTAL_DEFECTO_UUID, idioma="es", slug="cuenta", nombre="Cuenta"))
    db.add(CategoriaTraduccion(categoria_id="cuenta", portal_id=PORTAL_DEFECTO_UUID, idioma="pt", slug="conta", nombre="Conta"))
    db.add(
        AdminUser(
            portal_id=PORTAL_DEFECTO_UUID,
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            nivel=NivelAcceso.ADMINISTRADOR.value,
            activo=True,
        )
    )
    db.add(
        AdminUser(
            portal_id=PORTAL_DEFECTO_UUID,
            email=EDITOR_EMAIL,
            password_hash=hash_password(EDITOR_PASSWORD),
            nivel=NivelAcceso.EDITOR.value,
            activo=True,
        )
    )
    # El nombre de empresa vive en `Portal.nombre_empresa` (ya sembrado arriba); esta
    # fila guarda solo la marca visual (acento/banner/logo), con sus valores por defecto.
    db.add(Ajustes(id=AJUSTES_ID, portal_id=PORTAL_DEFECTO_UUID))
    db.add(
        PreguntaSinResolver(
            portal_id=PORTAL_DEFECTO_UUID,
            idioma="es", pregunta="¿Cómo cambio mi contraseña?", veces=10,
            similitud=0.5, fecha=date(2026, 7, 20), estado="nueva", orden=0,
        )
    )
    for idioma in ("es", "pt"):
        db.add(Conversacion(portal_id=PORTAL_DEFECTO_UUID, idioma=idioma, mensajes=[{"autor": "usuario", "texto": "hola"}]))
        db.add(Metrica(portal_id=PORTAL_DEFECTO_UUID, idioma=idioma, clave="sinResolver", valor="34", orden=0))
    db.commit()


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite no aplica las claves foráneas salvo que se active por conexión. Se
    # enciende para que el cascade y las FK diferibles se comporten como en
    # PostgreSQL (la base real), y los tests de integridad sean fieles.
    @event.listens_for(engine, "connect")
    def _activar_fk(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()
    _sembrar_minimo(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # `base_url` fija el host de las peticiones a `localhost`, que el seed mínimo mapea
    # al portal `default` en la tabla `dominios`. El portal se resuelve en el servidor a
    # partir de ese host (nunca del cliente), como en producción.
    yield TestClient(app, base_url="http://localhost")
    app.dependency_overrides.clear()


@pytest.fixture
def token(client) -> str:
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def editor_token(client) -> str:
    r = client.post("/api/auth/login", json={"email": EDITOR_EMAIL, "password": EDITOR_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def editor_auth(editor_token) -> dict:
    return {"Authorization": f"Bearer {editor_token}"}


# --- Segundo portal, para las pruebas de aislamiento -------------------------
# Un portal aparte del `default`, con su propio host y su Administrador. El correo del
# admin coincide a propósito con el del `default` (`admin@test.local`): así se prueba
# que `(portal_id, email)` es único por portal y que una sesión no cruza de portal.
SEGUNDO_PORTAL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000003")
SEGUNDO_PORTAL_SLUG = "otra-marca"
SEGUNDO_PORTAL_HOST = "otra-marca.test"
SEGUNDO_ADMIN_EMAIL = ADMIN_EMAIL
SEGUNDO_ADMIN_PASSWORD = "secreto-de-prueba-b"


def sembrar_portal_secundario(db) -> None:
    """Crea un segundo portal activo con su host y su Administrador (para aislamiento)."""
    db.add(
        Portal(
            id=SEGUNDO_PORTAL_UUID,
            slug=SEGUNDO_PORTAL_SLUG,
            nombre_empresa="Otra Marca",
            estado="activo",
        )
    )
    db.add(Dominio(host=SEGUNDO_PORTAL_HOST, portal_id=SEGUNDO_PORTAL_UUID, principal=True))
    db.flush()
    db.add(
        AdminUser(
            portal_id=SEGUNDO_PORTAL_UUID,
            email=SEGUNDO_ADMIN_EMAIL,
            password_hash=hash_password(SEGUNDO_ADMIN_PASSWORD),
            nivel=NivelAcceso.ADMINISTRADOR.value,
            activo=True,
        )
    )
    # Su propia categoría "cuenta": MISMO id que la del `default`, pero fila distinta
    # (PK compuesta `(portal_id, id)`) con su propio nombre. Así el segundo portal es un
    # tenant real donde su Administrador puede crear artículos —la FK compuesta exige que
    # la categoría sea de ESTE portal, no la del `default`— y se prueba de paso que dos
    # portales reusan el mismo id/slug de categoría sin colisionar.
    db.add(Categoria(id="cuenta", portal_id=SEGUNDO_PORTAL_UUID, icono="usuario", orden=0))
    db.add(CategoriaTraduccion(categoria_id="cuenta", portal_id=SEGUNDO_PORTAL_UUID, idioma="es", slug="cuenta", nombre="Cuenta B"))
    db.add(CategoriaTraduccion(categoria_id="cuenta", portal_id=SEGUNDO_PORTAL_UUID, idioma="pt", slug="conta", nombre="Conta B"))
    db.commit()


# --- Portal de plataforma y SuperAdmin, para la gestión de portales ----------
# El SuperAdmin (nivel 4) vive en el portal de plataforma y entra por su host de gestión
# (`admin.localhost`), que la tabla `dominios` mapea a ese portal. Desde ahí gestiona
# todos los portales; el slug `platform` está reservado y no se sirve como contenido.
SUPERADMIN_EMAIL = "superadmin@test.local"
SUPERADMIN_PASSWORD = "secreto-de-superadmin"


def sembrar_plataforma(db) -> None:
    """Crea el portal de plataforma, su host de gestión de desarrollo y su SuperAdmin."""
    db.add(
        Portal(
            id=PORTAL_PLATAFORMA_UUID,
            slug=PORTAL_PLATAFORMA_SLUG,
            nombre_empresa="Plataforma",
            estado="activo",
        )
    )
    db.add(Dominio(host=PORTAL_PLATAFORMA_HOST_DEV, portal_id=PORTAL_PLATAFORMA_UUID, principal=True))
    db.flush()
    db.add(
        AdminUser(
            portal_id=PORTAL_PLATAFORMA_UUID,
            email=SUPERADMIN_EMAIL,
            password_hash=hash_password(SUPERADMIN_PASSWORD),
            nivel=NivelAcceso.SUPERADMIN.value,
            activo=True,
        )
    )
    db.commit()


@pytest.fixture
def superadmin_client(db_session):
    """Cliente cuyo host (`admin.localhost`) resuelve al portal de plataforma, para las
    peticiones del SuperAdmin. Comparte la misma sesión que `db_session`, así que otro
    `TestClient` a `localhost` ve los mismos datos (útil para comprobar la suspensión)."""
    sembrar_plataforma(db_session)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, base_url="http://admin.localhost")
    app.dependency_overrides.clear()


@pytest.fixture
def superadmin_auth(superadmin_client) -> dict:
    r = superadmin_client.post(
        "/api/auth/login", json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def categoria_valida(categoria_id: str = "facturacion") -> dict:
    """Payload de categoría bilingüe completo para los tests."""
    return {
        "id": categoria_id,
        "icono": "documento",
        "orden": 3,
        "es": {"slug": "facturacion", "nombre": "Facturación"},
        "pt": {"slug": "faturacao", "nombre": "Faturação"},
    }


def articulo_valido(articulo_id: str = "nuevo-articulo") -> dict:
    """Payload de artículo bilingüe completo para los tests.

    El slug es único por portal (`uq_articulo_trad_portal_slug`), así que se deriva del
    id para que dos artículos distintos no colisionen. Para el id por defecto se conservan
    los slugs históricos (`nuevo-articulo`/`novo-artigo`), que fijan otras pruebas.
    """
    if articulo_id == "nuevo-articulo":
        slug_es, slug_pt = "nuevo-articulo", "novo-artigo"
    else:
        slug_es, slug_pt = f"{articulo_id}-es", f"{articulo_id}-pt"
    trad = lambda slug, titulo: {
        "slug": slug,
        "titulo": titulo,
        "parrafos": ["Un párrafo."],
        "howTo": {"titulo": "Pasos", "pasos": [{"titulo": "Paso 1", "descripcion": "Hazlo."}]},
        "nota": None,
        "faq": [{"pregunta": "¿Y?", "respuesta": "Pues eso."}],
    }
    return {
        "id": articulo_id,
        "categoria": "cuenta",
        "actualizado": "2026-07-25",
        "minutosLectura": 2,
        "destacado": True,
        "relacionados": [],
        "es": trad(slug_es, "Nuevo artículo"),
        "pt": trad(slug_pt, "Novo artigo"),
    }
