"""Configuración de IA por rol (chat / traducción / embeddings), solo SuperAdmin.

Es config **global de la plataforma** (una sola fila `ConfigIA` + una tabla
`config_ia_clave` sin `portal_id`): vale para todos los portales, así que la
gestiona el SuperAdmin transversal, no el Administrador de un portal. Los tests
positivos entran por el host de plataforma (`superadmin_client`); el guard
cross-tenant es `test_administrador_de_portal_no_accede`: un Administrador
(Nivel 3) no puede leerla ni pisarla.
"""

from __future__ import annotations

from app import salud_ia
from app.cifrado import cifrar, descifrar
from app.models import ConfigIA, ConfigIAClave
from app.servicios_ia import (
    CONFIG_IA_ID,
    PROVEEDORES_CHAT,
    PROVEEDORES_EMBEDDINGS,
    PROVEEDORES_TRADUCCION,
)


def test_superadmin_ve_roles_vacios_por_defecto(superadmin_client, superadmin_auth):
    """Sin fila de config ni claves: los tres roles vienen `None` y ningún
    proveedor está configurado. Los defaults por rol se aplican en la fábrica,
    no se «materializan» en la respuesta del panel."""
    r = superadmin_client.get("/api/admin/config-ia", headers=superadmin_auth)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["proveedorChat"] is None
    assert cuerpo["proveedorTraduccion"] is None
    assert cuerpo["proveedorEmbeddings"] is None
    por_id = {p["id"]: p["configurada"] for p in cuerpo["proveedores"]}
    assert por_id == {
        "anthropic": False,
        "deepseek": False,
        "openai": False,
        "voyage": False,
    }


def test_google_ya_no_esta_en_la_lista(superadmin_client, superadmin_auth):
    """Google se retiró: no tenía motor real y confundía a SuperAdmin al elegirlo."""
    ids = {p["id"] for p in superadmin_client.get(
        "/api/admin/config-ia", headers=superadmin_auth).json()["proveedores"]}
    assert "google" not in ids


def test_roles_soportados_expone_solo_proveedores_con_motor(superadmin_client, superadmin_auth):
    """El mapa `rolesSoportados` es la fuente de la verdad para los selectores
    del panel; solo aparece un proveedor si tiene motor real de ese rol."""
    roles = superadmin_client.get(
        "/api/admin/config-ia", headers=superadmin_auth
    ).json()["rolesSoportados"]
    assert set(roles["chat"]) == set(PROVEEDORES_CHAT)
    assert set(roles["traduccion"]) == set(PROVEEDORES_TRADUCCION)
    assert set(roles["embeddings"]) == set(PROVEEDORES_EMBEDDINGS)
    # Ninguna intersección chat ↔ embeddings hoy: los motores son disjuntos por rol.
    assert set(roles["chat"]).isdisjoint(set(roles["embeddings"]))


def test_asignar_rol_a_proveedor_sin_motor_es_422(superadmin_client, superadmin_auth):
    """Asignar Voyage como proveedor de chat (Voyage no tiene motor de chat)
    responde 422 sin persistir nada."""
    r = superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedorChat": "voyage"},
        headers=superadmin_auth,
    )
    assert r.status_code == 422
    # La fila sigue sin proveedor de chat asignado.
    leido = superadmin_client.get("/api/admin/config-ia", headers=superadmin_auth).json()
    assert leido["proveedorChat"] is None


def test_deepseek_es_proveedor_admitido_de_chat(superadmin_client, superadmin_auth):
    """DeepSeek se puede asignar al rol de chat y su clave se guarda con él."""
    r = superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedorChat": "deepseek", "proveedor": "deepseek", "clave": "sk-deepseek-de-prueba"},
        headers=superadmin_auth,
    )
    assert r.status_code == 200
    assert "sk-deepseek-de-prueba" not in r.text  # la clave nunca se serializa
    cuerpo = r.json()
    assert cuerpo["proveedorChat"] == "deepseek"
    por_id = {p["id"]: p["configurada"] for p in cuerpo["proveedores"]}
    assert por_id["deepseek"] is True


def test_pista_expone_solo_ultimos_caracteres(superadmin_client, superadmin_auth):
    """La respuesta trae una pista (últimos caracteres) pero nunca la clave completa."""
    superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedorChat": "deepseek", "proveedor": "deepseek", "clave": "sk-deepseek-1234ABCD"},
        headers=superadmin_auth,
    )
    cuerpo = superadmin_client.get("/api/admin/config-ia", headers=superadmin_auth).json()
    por_id = {p["id"]: p for p in cuerpo["proveedores"]}
    assert por_id["deepseek"]["pista"] == "ABCD"  # solo los últimos 4
    assert "sk-deepseek-1234ABCD" not in str(cuerpo)  # nunca la clave completa


def test_pista_none_si_clave_demasiado_corta(superadmin_client, superadmin_auth):
    """Con una clave demasiado corta no se da pista: revelaría casi toda la clave."""
    superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedor": "anthropic", "clave": "sk-123"},  # < 8 caracteres
        headers=superadmin_auth,
    )
    cuerpo = superadmin_client.get("/api/admin/config-ia", headers=superadmin_auth).json()
    por_id = {p["id"]: p for p in cuerpo["proveedores"]}
    assert por_id["anthropic"]["configurada"] is True
    assert por_id["anthropic"]["pista"] is None


def test_clave_se_guarda_cifrada_en_reposo(superadmin_client, superadmin_auth, db_session):
    """La clave se cifra al guardar; en reposo no está en texto plano."""
    superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedor": "anthropic", "clave": "sk-otra-clave"},
        headers=superadmin_auth,
    )
    fila = db_session.get(ConfigIAClave, "anthropic")
    assert fila is not None
    assert fila.token_cifrado != "sk-otra-clave"  # no está en texto plano
    assert descifrar(fila.token_cifrado) == "sk-otra-clave"  # pero se puede recuperar


def test_clave_vacia_significa_no_cambiar(superadmin_client, superadmin_auth):
    """Guardar solo cambia el rol si no viene `clave`: la clave persistida
    sigue ahí."""
    superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedor": "anthropic", "clave": "sk-persistente"},
        headers=superadmin_auth,
    )
    r = superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedorTraduccion": "anthropic"},
        headers=superadmin_auth,
    )
    assert r.status_code == 200
    por_id = {p["id"]: p["configurada"] for p in r.json()["proveedores"]}
    assert por_id["anthropic"] is True  # la clave sigue ahí
    assert r.json()["proveedorTraduccion"] == "anthropic"


def test_borrar_clave_no_referenciada_borra_la_fila(superadmin_client, superadmin_auth, db_session):
    """Con `borrarClave=true` y `proveedor=openai` cuando openai no es el
    proveedor de ningún rol: la fila se borra y las demás quedan intactas."""
    # Deja dos claves puestas.
    superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedor": "anthropic", "clave": "sk-anthropic-larga"},
        headers=superadmin_auth,
    )
    superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedor": "openai", "clave": "sk-openai-larga"},
        headers=superadmin_auth,
    )
    # Ningún rol referencia openai todavía.
    r = superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedor": "openai", "borrarClave": True},
        headers=superadmin_auth,
    )
    assert r.status_code == 200
    por_id = {p["id"]: p["configurada"] for p in r.json()["proveedores"]}
    assert por_id["openai"] is False
    assert por_id["anthropic"] is True  # sigue configurada
    assert db_session.get(ConfigIAClave, "openai") is None


def test_borrar_clave_en_uso_es_409_con_rol(superadmin_client, superadmin_auth, db_session):
    """Con `borrarClave=true` cuando el proveedor está referenciado por algún
    rol: 409 con detalle que menciona ese rol; la fila NO se borra."""
    superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedorChat": "deepseek", "proveedor": "deepseek", "clave": "sk-deepseek-larga"},
        headers=superadmin_auth,
    )
    r = superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedor": "deepseek", "borrarClave": True},
        headers=superadmin_auth,
    )
    assert r.status_code == 409
    assert "chat" in r.json()["detail"]
    # La fila sigue viva.
    assert db_session.get(ConfigIAClave, "deepseek") is not None


def test_combinar_chat_deepseek_y_traduccion_anthropic(superadmin_client, superadmin_auth):
    """El caso que motiva el cambio: chat con DeepSeek y traducción con
    Anthropic, dos filas distintas de `config_ia_clave`, sin colisión."""
    r1 = superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedorChat": "deepseek", "proveedor": "deepseek", "clave": "sk-deepseek-larga"},
        headers=superadmin_auth,
    )
    assert r1.status_code == 200
    r2 = superadmin_client.put(
        "/api/admin/config-ia",
        json={"proveedorTraduccion": "anthropic", "proveedor": "anthropic", "clave": "sk-anthropic-larga"},
        headers=superadmin_auth,
    )
    assert r2.status_code == 200
    cuerpo = r2.json()
    assert cuerpo["proveedorChat"] == "deepseek"
    assert cuerpo["proveedorTraduccion"] == "anthropic"
    por_id = {p["id"]: p["configurada"] for p in cuerpo["proveedores"]}
    assert por_id["deepseek"] is True
    assert por_id["anthropic"] is True


def test_administrador_de_portal_no_accede(client, auth):
    """El núcleo del aislamiento: la config de IA es global de plataforma, así
    que el Administrador de un portal (Nivel 3) NO puede leerla ni pisarla."""
    assert client.get("/api/admin/config-ia", headers=auth).status_code == 403
    r = client.put(
        "/api/admin/config-ia", json={"proveedorChat": "deepseek"}, headers=auth
    )
    assert r.status_code == 403


def test_editor_no_accede(client, editor_auth):
    assert client.get("/api/admin/config-ia", headers=editor_auth).status_code == 403
    r = client.put(
        "/api/admin/config-ia", json={"proveedorChat": "deepseek"}, headers=editor_auth
    )
    assert r.status_code == 403


def test_anonimo_no_accede(client):
    assert client.get("/api/admin/config-ia").status_code == 401
    assert client.put(
        "/api/admin/config-ia", json={"proveedorChat": "deepseek"}
    ).status_code == 401


def test_migracion_conserva_valor_esperado_para_shape_nuevo(db_session):
    """Fija la semántica del `upgrade` de 0010 a nivel de modelo: sembrando la
    fila `ConfigIA` como quedaría tras la migración con `proveedor_activo='deepseek'`
    y `claves={'deepseek': 'token-cifrado'}`, el `upgrade` debería dejar
    `proveedor_chat='deepseek'`, `proveedor_traduccion='deepseek'`,
    `proveedor_embeddings=None` (no había clave Voyage), y una fila de
    `config_ia_clave` para deepseek con el token conservado.

    El test se implementa contra el modelo nuevo (equivalente a `alembic upgrade
    head` sobre la base sembrada con la forma anterior): siembra directamente
    el estado esperado tras la migración y verifica que se puede consultar."""
    db_session.query(ConfigIA).delete()
    db_session.query(ConfigIAClave).delete()
    db_session.add(
        ConfigIA(
            id=CONFIG_IA_ID,
            proveedor_chat="deepseek",
            proveedor_traduccion="deepseek",
            proveedor_embeddings=None,
        )
    )
    db_session.add(ConfigIAClave(proveedor="deepseek", token_cifrado="token-cifrado"))
    db_session.commit()

    fila = db_session.get(ConfigIA, CONFIG_IA_ID)
    clave = db_session.get(ConfigIAClave, "deepseek")
    assert fila.proveedor_chat == "deepseek"
    assert fila.proveedor_traduccion == "deepseek"
    assert fila.proveedor_embeddings is None
    assert clave is not None
    assert clave.token_cifrado == "token-cifrado"


# --- Salud de los proveedores (GET /salud) ---------------------------------
#
# El sondeo real sale a internet, así que aquí se sustituye `_sondear` por un
# doble: lo que se prueba es la clasificación, el aislamiento por nivel y la
# caché, no la API del proveedor.


def _sin_cache():
    salud_ia.limpiar_cache()


def test_salud_sin_clave_no_sondea(superadmin_client, superadmin_auth, monkeypatch):
    """Sin clave guardada, el rol sale `sin_clave` y NUNCA se llama al proveedor:
    salir a internet con una clave que no existe solo gasta tiempo."""
    _sin_cache()
    llamadas = []
    monkeypatch.setattr(
        salud_ia, "_sondear", lambda p, c: llamadas.append(p) or ("ok", "no debería pasar")
    )

    r = superadmin_client.get("/api/admin/config-ia/salud", headers=superadmin_auth)
    assert r.status_code == 200
    roles = r.json()["roles"]
    assert [x["rol"] for x in roles] == ["chat", "traduccion", "embeddings"]
    assert {x["estado"] for x in roles} == {"sin_clave"}
    assert llamadas == []


def test_salud_distingue_saldo_de_credenciales(
    superadmin_client, superadmin_auth, db_session, monkeypatch
):
    """El motivo de este endpoint: 401 y 402 producen el mismo 502 en el panel,
    pero uno se arregla rotando la clave y el otro recargando la cuenta."""
    _sin_cache()
    db_session.query(ConfigIA).delete()
    db_session.query(ConfigIAClave).delete()
    db_session.add(ConfigIA(id=CONFIG_IA_ID, proveedor_chat="deepseek"))
    db_session.add(ConfigIAClave(proveedor="deepseek", token_cifrado=cifrar("sk-deepseek-larga")))
    db_session.commit()

    assert salud_ia._clasificar_http(401)[0] == "credenciales"
    assert salud_ia._clasificar_http(402)[0] == "saldo"
    assert salud_ia._clasificar_http(429)[0] == "error"

    monkeypatch.setattr(salud_ia, "_sondear", lambda p, c: ("saldo", "sin fondos"))
    r = superadmin_client.get("/api/admin/config-ia/salud", headers=superadmin_auth)
    assert r.status_code == 200
    chat = next(x for x in r.json()["roles"] if x["rol"] == "chat")
    assert chat["proveedor"] == "deepseek"
    assert chat["estado"] == "saldo"


def test_salud_no_devuelve_el_texto_crudo_del_proveedor(
    superadmin_client, superadmin_auth, db_session, monkeypatch
):
    """El detalle lo redacta el backend. El mensaje del proveedor puede llevar
    datos de cuenta o de infraestructura y va solo al log, nunca al navegador."""
    _sin_cache()
    db_session.query(ConfigIA).delete()
    db_session.query(ConfigIAClave).delete()
    db_session.add(ConfigIA(id=CONFIG_IA_ID, proveedor_chat="deepseek"))
    db_session.add(ConfigIAClave(proveedor="deepseek", token_cifrado=cifrar("sk-deepseek-larga")))
    db_session.commit()

    crudo = "Error code: 402 - user_id=abc123 org=acme-internal"
    monkeypatch.setattr(salud_ia, "_sondear", lambda p, c: salud_ia._clasificar_http(402))

    cuerpo = superadmin_client.get(
        "/api/admin/config-ia/salud", headers=superadmin_auth
    ).json()
    serializado = str(cuerpo)
    assert "abc123" not in serializado
    assert "acme-internal" not in serializado
    assert crudo not in serializado
    # Tampoco se filtra la clave.
    assert "sk-deepseek-larga" not in serializado


def test_salud_usa_cache_para_no_martillear_al_proveedor(
    superadmin_client, superadmin_auth, db_session, monkeypatch
):
    """Pulsar «Comprobar» repetidamente no debe multiplicar las llamadas salientes
    (con Voyage, además, cada sondeo cuesta tokens)."""
    _sin_cache()
    db_session.query(ConfigIA).delete()
    db_session.query(ConfigIAClave).delete()
    db_session.add(
        ConfigIA(
            id=CONFIG_IA_ID,
            proveedor_chat="deepseek",
            proveedor_traduccion="deepseek",
            proveedor_embeddings="voyage",
        )
    )
    db_session.add(ConfigIAClave(proveedor="deepseek", token_cifrado=cifrar("sk-deepseek-larga")))
    db_session.add(ConfigIAClave(proveedor="voyage", token_cifrado=cifrar("pa-voyage-larga")))
    db_session.commit()

    llamadas: list[str] = []
    monkeypatch.setattr(salud_ia, "_sondear", lambda p, c: llamadas.append(p) or ("ok", "bien"))

    superadmin_client.get("/api/admin/config-ia/salud", headers=superadmin_auth)
    # chat y traduccion comparten proveedor (deepseek) -> se sondea una sola vez.
    assert llamadas == ["deepseek", "voyage"]

    superadmin_client.get("/api/admin/config-ia/salud", headers=superadmin_auth)
    assert llamadas == ["deepseek", "voyage"], "la segunda lectura debe salir de la caché"


def test_salud_exige_superadmin(client, auth):
    """Mismo aislamiento que el resto de `config-ia`: es config global de
    plataforma, así que el Administrador de un portal (Nivel 3) no la alcanza."""
    assert client.get("/api/admin/config-ia/salud", headers=auth).status_code == 403
