"""Configuración de IA por rol (chat / traducción / embeddings), reservada a SuperAdmin (Nivel 4).

Es configuración **global de la plataforma** (fila única, sin `portal_id`): los proveedores y
las claves que devuelve valen para todos los portales. Por eso la gestiona solo el SuperAdmin
transversal, no el Administrador de un portal —que solo debe poder tocar lo suyo—. Si la
gobernara el Administrador (Nivel 3), el admin de un tenant podría sobrescribir la clave/
proveedor que usan los demás portales (fuga cross-tenant); ver revisión de Sección 9 del
cambio `multi-tenant-portales`.

La configuración se modela como **tres roles independientes**: `proveedorChat`,
`proveedorTraduccion` y `proveedorEmbeddings`. Cada rol se cambia por separado y solo admite
proveedores con motor real para ese rol (el mapa `rolesSoportados` que sale del GET filtra
los selectores del panel; el PUT valida contra el mismo mapa y responde 422 si el proveedor
no es viable). Las claves de API viven en la tabla `config_ia_clave` (una fila por proveedor,
cifrada), no dentro de `ConfigIA`.

La clave de API completa nunca se devuelve al cliente: la lectura informa de si cada
proveedor tiene clave (`configurada`) y expone solo una **pista** (sus últimos caracteres)
para que SuperAdmin reconozca cuál está puesta. La escritura la cifra en reposo. Dejar la
clave vacía significa «no cambiarla». `borrarClave=true` con `proveedor` borra su fila,
salvo que ese proveedor esté referenciado por algún rol (409 con detalle legible).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.cifrado import CifradoNoConfigurado, cifrar, descifrar
from app.database import get_db
from app.deps import requiere_nivel
from app.models import ConfigIA, ConfigIAClave, NivelAcceso
from app.salud_ia import comprobar_todos
from app.schemas import (
    ConfigIAIn,
    ConfigIAOut,
    ProveedorEstado,
    RolesSoportadosOut,
    SaludIAOut,
    SaludRolOut,
)
from app.servicios_ia import (
    CONFIG_IA_ID,
    PROVEEDORES_CHAT,
    PROVEEDORES_EMBEDDINGS,
    PROVEEDORES_TRADUCCION,
)

# Proveedores admitidos en la lista de estado (coincide con el `Literal ProveedorIA`
# de schemas). Cada uno tiene motor real en algunos roles y no en otros; el filtro
# por rol lo aplica `rolesSoportados`.
PROVEEDORES: tuple[str, ...] = ("anthropic", "deepseek", "openai", "voyage")

# Nº de caracteres finales que se revelan como pista y longitud mínima de clave
# para revelarlos: por debajo de este umbral, mostrar el final descubriría casi
# toda la clave, así que no se da pista (se informa solo de que está configurada).
PISTA_CARACTERES = 4
PISTA_LONGITUD_MINIMA = 8


def _pista(token: str | None) -> str | None:
    """Últimos caracteres de la clave cifrada `token`, o `None` si no hay clave,
    no puede descifrarse (falta/rota la clave de cifrado) o es demasiado corta."""
    if not token:
        return None
    try:
        clave = descifrar(token)
    except CifradoNoConfigurado:
        return None
    if len(clave) < PISTA_LONGITUD_MINIMA:
        return None
    return clave[-PISTA_CARACTERES:]


router = APIRouter(
    prefix="/api/admin/config-ia",
    tags=["admin", "ia"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.SUPERADMIN))],
)


def _tokens_por_proveedor(db: Session) -> dict[str, str]:
    """Diccionario `{proveedor: token_cifrado}` con las filas de `config_ia_clave`."""
    return {fila.proveedor: fila.token_cifrado for fila in db.query(ConfigIAClave).all()}


def _a_salida(config: ConfigIA | None, tokens: dict[str, str]) -> ConfigIAOut:
    return ConfigIAOut(
        proveedorChat=(config.proveedor_chat if config is not None else None),
        proveedorTraduccion=(config.proveedor_traduccion if config is not None else None),
        proveedorEmbeddings=(config.proveedor_embeddings if config is not None else None),
        proveedores=[
            ProveedorEstado(
                id=p, configurada=bool(tokens.get(p)), pista=_pista(tokens.get(p))
            )
            for p in PROVEEDORES
        ],
        rolesSoportados=RolesSoportadosOut(
            chat=list(PROVEEDORES_CHAT),
            traduccion=list(PROVEEDORES_TRADUCCION),
            embeddings=list(PROVEEDORES_EMBEDDINGS),
        ),
    )


def _rol_que_usa(config: ConfigIA | None, datos: ConfigIAIn, proveedor: str) -> str | None:
    """Rol que está referenciando `proveedor`, mirando primero el cuerpo del PUT y
    después la fila persistida. Devuelve el nombre del rol en español para el
    mensaje de error, o `None` si nadie lo está usando."""
    # Efectivo tras aplicar los cambios del cuerpo: `datos.proveedorX` sobrescribe
    # a la fila cuando viene no-None; si viene None, prevalece el valor persistido.
    def efectivo(campo_cuerpo: str | None, campo_fila: str | None) -> str | None:
        return campo_cuerpo if campo_cuerpo is not None else campo_fila

    chat = efectivo(datos.proveedorChat, config.proveedor_chat if config else None)
    trad = efectivo(datos.proveedorTraduccion, config.proveedor_traduccion if config else None)
    emb = efectivo(datos.proveedorEmbeddings, config.proveedor_embeddings if config else None)
    if chat == proveedor:
        return "chat"
    if trad == proveedor:
        return "traduccion"
    if emb == proveedor:
        return "embeddings"
    return None


@router.get("", response_model=ConfigIAOut)
def obtener(db: Session = Depends(get_db)) -> ConfigIAOut:
    return _a_salida(db.get(ConfigIA, CONFIG_IA_ID), _tokens_por_proveedor(db))


@router.get("/salud", response_model=SaludIAOut)
def salud(db: Session = Depends(get_db)) -> SaludIAOut:
    """Sondea cada rol contra su proveedor y devuelve un estado clasificado.

    Existe para que un fallo de proveedor (clave revocada, cuenta sin saldo, caída)
    sea visible desde el panel en vez de solo desde los logs: el chat degrada a
    `escalar` en silencio y las sugerencias devuelven un 502 genérico, así que
    ninguna de las dos superficies delataba la causa.

    Es una llamada saliente real, así que va **bajo demanda** (un botón), con
    timeout corto y caché en proceso; ver `app.salud_ia`.
    """
    return SaludIAOut(
        roles=[
            SaludRolOut(
                rol=r.rol,
                proveedor=r.proveedor,
                estado=r.estado,
                detalle=r.detalle,
                comprobadoEn=r.comprobado_en,
            )
            for r in comprobar_todos(db)
        ]
    )


@router.put("", response_model=ConfigIAOut)
def actualizar(datos: ConfigIAIn, db: Session = Depends(get_db)) -> ConfigIAOut:
    config = db.get(ConfigIA, CONFIG_IA_ID)
    if config is None:
        config = ConfigIA(id=CONFIG_IA_ID)
        db.add(config)

    # 1) Aplicar los cambios de rol (None = «no cambiar»). Cada asignación se
    #    valida contra `rolesSoportados[rol]`: un proveedor sin motor de ese rol
    #    (p. ej. Voyage como chat) se rechaza con 422 sin persistir nada.
    if datos.proveedorChat is not None:
        if datos.proveedorChat not in PROVEEDORES_CHAT:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"El proveedor '{datos.proveedorChat}' no soporta el rol 'chat'.",
            )
        config.proveedor_chat = datos.proveedorChat
    if datos.proveedorTraduccion is not None:
        if datos.proveedorTraduccion not in PROVEEDORES_TRADUCCION:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"El proveedor '{datos.proveedorTraduccion}' no soporta el rol 'traduccion'.",
            )
        config.proveedor_traduccion = datos.proveedorTraduccion
    if datos.proveedorEmbeddings is not None:
        if datos.proveedorEmbeddings not in PROVEEDORES_EMBEDDINGS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"El proveedor '{datos.proveedorEmbeddings}' no soporta el rol 'embeddings'.",
            )
        config.proveedor_embeddings = datos.proveedorEmbeddings

    # 2) Borrado de clave (excluye escritura). Requiere `proveedor` y prohíbe
    #    borrar la clave de un proveedor referenciado por algún rol.
    if datos.borrarClave:
        if datos.clave:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No se puede borrar y actualizar la clave en la misma petición.",
            )
        if not datos.proveedor:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Para borrar una clave hay que indicar el proveedor.",
            )
        rol_en_uso = _rol_que_usa(config, datos, datos.proveedor)
        if rol_en_uso is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"El proveedor '{datos.proveedor}' está en uso por el rol '{rol_en_uso}'.",
            )
        fila = db.get(ConfigIAClave, datos.proveedor)
        if fila is not None:
            db.delete(fila)

    # 3) Escritura de clave. Clave vacía/ausente = no cambiar; en otro caso se
    #    cifra y se hace upsert (por PK) en `config_ia_clave`.
    elif datos.clave and datos.clave.strip():
        if not datos.proveedor:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Para guardar una clave hay que indicar el proveedor.",
            )
        try:
            token = cifrar(datos.clave.strip())
        except CifradoNoConfigurado as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Falta CLAVE_CIFRADO_IA en el servidor: no se puede guardar la clave.",
            ) from exc
        fila = db.get(ConfigIAClave, datos.proveedor)
        if fila is None:
            db.add(ConfigIAClave(proveedor=datos.proveedor, token_cifrado=token))
        else:
            fila.token_cifrado = token

    db.commit()
    db.refresh(config)
    return _a_salida(config, _tokens_por_proveedor(db))
