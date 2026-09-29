"""Hash de contraseñas (argon2) y ciclo de vida del JWT, sin pasar por la API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.security import crear_token, decodificar_token, hash_password, verify_password


def _firmar(payload: dict, secreto: str | None = None) -> str:
    s = get_settings()
    return jwt.encode(payload, secreto or s.jwt_secret, algorithm=s.jwt_algorithm)


# --- argon2 -----------------------------------------------------------------

def test_hash_no_guarda_la_contrasena_en_claro():
    resultado = hash_password("secreto")
    assert resultado != "secreto"
    assert resultado.startswith("$argon2")


def test_hash_usa_sal_aleatoria():
    # Dos hashes de la misma contraseña no coinciden: cada uno lleva su sal.
    assert hash_password("secreto") != hash_password("secreto")


def test_verify_acepta_la_contrasena_correcta():
    assert verify_password(hash_password("secreto"), "secreto") is True


def test_verify_rechaza_la_incorrecta():
    assert verify_password(hash_password("secreto"), "otra") is False


def test_verify_distingue_mayusculas():
    assert verify_password(hash_password("Secreto"), "secreto") is False


def test_verify_rechaza_la_cadena_vacia():
    assert verify_password(hash_password("secreto"), "") is False


# --- JWT --------------------------------------------------------------------

def test_token_ida_y_vuelta():
    datos = decodificar_token(crear_token("admin@test.local", "default"))
    assert datos is not None
    assert datos.email == "admin@test.local"
    assert datos.portal_id == "default"


def test_token_lleva_caducidad_y_portal():
    s = get_settings()
    payload = jwt.decode(crear_token("x", "default"), s.jwt_secret, algorithms=[s.jwt_algorithm])
    assert "exp" in payload
    assert payload["sub"] == "x"
    # El portal viaja en el token: sin él, un token del portal A serviría en el B.
    assert payload["portal"] == "default"


def test_token_sin_portal_devuelve_none():
    # Un token bien firmado pero sin `portal` (o con un valor no textual) no identifica
    # el portal y no puede autorizarse: se descarta como inválido.
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert decodificar_token(_firmar({"sub": "admin@test.local", "exp": exp})) is None
    assert decodificar_token(_firmar({"sub": "admin@test.local", "portal": 1, "exp": exp})) is None


def test_token_ilegible_devuelve_none():
    assert decodificar_token("no-es-un-jwt") is None
    assert decodificar_token("") is None


def test_token_firmado_con_otro_secreto_devuelve_none():
    ajeno = _firmar(
        {"sub": "admin@test.local", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        secreto="secreto-que-no-es-el-nuestro",
    )
    assert decodificar_token(ajeno) is None


def test_token_caducado_devuelve_none():
    caducado = _firmar({"sub": "admin@test.local", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)})
    assert decodificar_token(caducado) is None


def test_token_sin_sub_devuelve_none():
    sin_sub = _firmar({"exp": datetime.now(timezone.utc) + timedelta(minutes=5)})
    assert decodificar_token(sin_sub) is None


def test_token_con_sub_no_textual_devuelve_none():
    # `sub` numérico o nulo está bien firmado pero no identifica a nadie:
    # se descarta en vez de dejar que llegue a la consulta del administrador.
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert decodificar_token(_firmar({"sub": 123, "exp": exp})) is None
    assert decodificar_token(_firmar({"sub": None, "exp": exp})) is None


def test_token_sin_exp_sigue_siendo_valido():
    """PyJWT no exige `exp` por defecto; `crear_token` siempre lo pone.

    Se fija el comportamiento actual: si algún día se activa `require=["exp"]`,
    este test debe cambiar y no pasar desapercibido.
    """
    datos = decodificar_token(_firmar({"sub": "admin@test.local", "portal": "default"}))
    assert datos is not None
    assert datos.email == "admin@test.local"


def test_algoritmo_none_rechazado():
    # Ataque clásico: token sin firma declarando alg=none.
    sin_firma = jwt.encode(
        {"sub": "admin@test.local", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        key="",
        algorithm="none",
    )
    assert decodificar_token(sin_firma) is None
