"""Esquemas Pydantic. Reproducen el contrato `app/src/types.ts` campo a campo.

Los nombres usan camelCase (minutosLectura, howTo) para que el JSON coincida
exactamente con lo que el frontend ya consume.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.servicios import PLANTILLAS_ADMITIDAS

Idioma = Literal["es", "pt"]

# Cotas de tamaño para el contenido de artículo que entra por el panel (alta, edición
# y traducción). Son holgadas frente al contenido real de `app/src/data/{es,pt}` (la
# cadena más larga ronda los ~370 caracteres y ninguna lista pasa de unos pocos ítems),
# pero cortan payloads desmesurados antes de gastar el proveedor de IA en la traducción
# (defensa contra inyección de prompts y coste; ver cambio `guardarrailes-inyeccion-runtime`).
MAX_TEXTO_CORTO = 300  # títulos y preguntas
MAX_TEXTO_LARGO = 5000  # párrafos, notas, descripciones y respuestas
MAX_ITEMS_LISTA = 50  # nº de párrafos, pasos o preguntas por artículo

TextoCorto = Annotated[str, Field(min_length=1, max_length=MAX_TEXTO_CORTO)]
TextoLargo = Annotated[str, Field(max_length=MAX_TEXTO_LARGO)]


# --- Bloques de contenido ---------------------------------------------------

# Conjunto cerrado de iconos que el frontend sabe renderizar (`app/src/components/
# iconos.tsx`, tipo `NombreIcono` en `app/src/types.ts`). El servidor rechaza con 422
# cualquier valor fuera de este conjunto: antes era texto libre y un valor sin
# componente asociado rompía el render público. `None` («sin icono») se admite aparte,
# en cada campo `icono`, no como un valor más del conjunto.
IconoCategoria = Literal[
    "usuario", "tarjeta", "paquete", "devolver", "escudo", "documento",
    # Iconos de desarrollo (portales de documentación técnica).
    "codigo", "terminal", "git", "base-datos", "servidor", "nube",
    "api", "bug", "llave", "cpu", "libro", "cohete",
]


class CategoriaOut(BaseModel):
    id: str
    slug: str
    nombre: str
    # Nulo = sin icono. Con `response_model_exclude_none` del contenido público la clave
    # no viaja; el frontend trata la ausencia como «sin icono».
    icono: str | None = None


class PasoHowTo(BaseModel):
    titulo: TextoCorto
    descripcion: TextoLargo


class BloqueHowTo(BaseModel):
    titulo: TextoCorto
    pasos: list[PasoHowTo] = Field(max_length=MAX_ITEMS_LISTA)


class PreguntaFrecuente(BaseModel):
    pregunta: TextoCorto
    respuesta: TextoLargo


class ArticuloOut(BaseModel):
    id: str
    slug: str
    titulo: str
    categoria: str
    actualizado: str
    minutosLectura: int
    destacado: bool
    parrafos: list[str]
    howTo: BloqueHowTo
    nota: str | None = None
    faq: list[PreguntaFrecuente]
    relacionados: list[str]


class MetricaOut(BaseModel):
    clave: str
    valor: str


class ContenidoIdiomaOut(BaseModel):
    """Contenido público de un idioma.

    No incluye las preguntas sin resolver: son texto escrito por las personas
    usuarias y solo se sirven por el router de administración, autenticado.
    """

    empresa: str
    # Marca visual pública: alimenta los tokens de acento y el degradado del banner
    # en el HTML servido (SSR). El logo no viaja aquí (se sirve por `/api/marca/logo`).
    acento: str
    bannerDesde: str
    bannerMedio: str
    bannerHasta: str
    # Plantilla activa del portal (`default` o `documentacion`). Viaja siempre presente:
    # es lo que permite que el HTML inicial se sirva ya con el armazón correcto.
    plantilla: str
    # URL del repositorio de GitHub del portal, o nula (no viaja: `exclude_none`).
    githubUrl: str | None = None
    # Indica si hay logotipo subido (para cabecera y favicon); el binario no viaja aquí.
    logo: bool
    # Hash corto de los bytes del logo (o null sin logo). Se usa como cache-buster en
    # la URL del `<img>` para que al cambiar el logotipo el navegador vuelva a pedirlo
    # y no reutilice la copia cacheada de la URL anterior.
    logoVersion: str | None = None
    categorias: list[CategoriaOut]
    articulos: list[ArticuloOut]
    conversacion: list[dict[str, Any]]
    metricas: list[MetricaOut]


# --- Autenticación ----------------------------------------------------------

class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    # El BFF (servidor de frontend de confianza) recibe ambos tokens y los guarda
    # en cookies httpOnly; nunca llegan al JavaScript del navegador.
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    # Opcional: el logout siempre limpia la sesión del cliente; si llega el
    # refresh token, además se revoca su familia en el servidor.
    refresh_token: str | None = None


# --- CRUD de artículos (entrada bilingüe) -----------------------------------

class TraduccionArticuloIn(BaseModel):
    slug: str = Field(min_length=1, max_length=MAX_TEXTO_CORTO)
    titulo: TextoCorto
    parrafos: list[TextoLargo] = Field(max_length=MAX_ITEMS_LISTA)
    howTo: BloqueHowTo
    nota: TextoLargo | None = None
    faq: list[PreguntaFrecuente] = Field(max_length=MAX_ITEMS_LISTA)


class ArticuloIn(BaseModel):
    """Artículo bilingüe: `es` y `pt` son obligatorios (paridad de idiomas)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    categoria: str
    actualizado: str  # AAAA-MM-DD
    minutosLectura: int = Field(ge=0)
    destacado: bool = False
    relacionados: list[str] = Field(default_factory=list)
    es: TraduccionArticuloIn
    pt: TraduccionArticuloIn


class ArticuloUpdateIn(BaseModel):
    """Como `ArticuloIn` pero sin `id` (viene de la ruta)."""

    model_config = ConfigDict(extra="forbid")

    categoria: str
    actualizado: str
    minutosLectura: int = Field(ge=0)
    destacado: bool = False
    relacionados: list[str] = Field(default_factory=list)
    es: TraduccionArticuloIn
    pt: TraduccionArticuloIn


class ArticuloAdminOut(BaseModel):
    """Artículo con sus dos idiomas, para editar en el panel."""

    id: str
    categoria: str
    actualizado: str
    minutosLectura: int
    destacado: bool
    relacionados: list[str]
    es: TraduccionArticuloIn
    pt: TraduccionArticuloIn


# --- CRUD de categorías (entrada bilingüe) ----------------------------------

class TraduccionCategoriaIn(BaseModel):
    slug: str = Field(min_length=1, max_length=MAX_TEXTO_CORTO)
    nombre: TextoCorto


class CategoriaIn(BaseModel):
    """Categoría bilingüe: `es` y `pt` son obligatorios (paridad de idiomas).

    Espejo de `Categoria`/`CategoriaTraduccion`: la entidad estable lleva la
    presentación (icono, orden) y cada idioma su nombre y slug. La categoría NO
    lleva color propio: su presentación en el contenido público se deriva siempre
    del acento del portal (ver `personalizacion-paleta`).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    # Obligatorio en el cuerpo (explícito): `null` significa «sin icono».
    icono: IconoCategoria | None
    orden: int = Field(default=0, ge=0)
    es: TraduccionCategoriaIn
    pt: TraduccionCategoriaIn


class CategoriaUpdateIn(BaseModel):
    """Como `CategoriaIn` pero sin `id` (viene de la ruta)."""

    model_config = ConfigDict(extra="forbid")

    icono: IconoCategoria | None
    orden: int = Field(default=0, ge=0)
    es: TraduccionCategoriaIn
    pt: TraduccionCategoriaIn


class CategoriaAdminOut(BaseModel):
    """Categoría con sus dos idiomas, para gestionar en el panel.

    Distinta de `CategoriaOut` (proyección pública de un solo idioma que viaja en
    el contenido), como `ArticuloAdminOut` lo es de `ArticuloOut`.
    """

    id: str
    icono: str | None
    orden: int
    es: TraduccionCategoriaIn
    pt: TraduccionCategoriaIn


# --- Panel: preguntas sin resolver ------------------------------------------

class PreguntaAdminOut(BaseModel):
    id: int
    idioma: str
    pregunta: str
    veces: int
    similitud: float
    fecha: str
    estado: str


# --- Sesión y niveles -------------------------------------------------------

# Nivel asignable a un usuario: Editor (2) o Administrador (3). Anónimo (1) no se
# asigna nunca (es la ausencia de sesión), así que se excluye del contrato.
NivelAsignable = Literal[2, 3]

# Contraseña mínima para cuentas creadas por la API, alineada con el seed.
LONGITUD_MINIMA_CONTRASENA = 12


class MeOut(BaseModel):
    """Identidad de la sesión actual: el frontend la usa para ajustar la UI a su nivel."""

    email: str
    nivel: int


# --- Gestión de usuarios (solo Administrador) -------------------------------

class UsuarioOut(BaseModel):
    """Usuario administrable. Nunca incluye el hash de la contraseña."""

    id: int
    email: str
    nivel: int
    activo: bool
    creado: str


class UsuarioCrearIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3)
    password: str = Field(min_length=LONGITUD_MINIMA_CONTRASENA)
    nivel: NivelAsignable


class UsuarioActualizarIn(BaseModel):
    """Edita correo y nivel; la contraseña es opcional (reset)."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3)
    nivel: NivelAsignable
    password: str | None = Field(default=None, min_length=LONGITUD_MINIMA_CONTRASENA)


# --- Gestión de portales (solo SuperAdmin) ----------------------------------

# Slug de portal: minúsculas ASCII, dígitos y guiones internos; empieza y acaba en
# alfanumérico. Es la base del subdominio `<slug>.<base_domain>`, así que se ciñe a lo
# que admite una etiqueta de host (sin puntos, sin guiones al borde, ≤63 caracteres). La
# unicidad y la colisión con slugs reservados las valida el router (autoridad del servidor).
SlugPortal = Annotated[
    str,
    Field(min_length=2, max_length=63, pattern=r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"),
]


class PortalCrearIn(BaseModel):
    """Alta de un portal por el SuperAdmin: sus atributos y su Administrador inicial.

    El portal nace activo, con su fila de marca por defecto y su Administrador (nivel 3)
    acotado a él. No lleva `es`/`pt`: un portal no es contenido bilingüe.
    """

    model_config = ConfigDict(extra="forbid")

    slug: SlugPortal
    nombreEmpresa: str = Field(min_length=1, max_length=MAX_TEXTO_CORTO)
    adminEmail: str = Field(min_length=3)
    adminPassword: str = Field(min_length=LONGITUD_MINIMA_CONTRASENA)


class PortalOut(BaseModel):
    """Portal para el listado del SuperAdmin: identidad, estado y su host canónico."""

    id: str
    slug: str
    nombreEmpresa: str
    estado: str
    # Host principal (subdominio) por el que se sirve el portal; `None` si aún no tiene.
    host: str | None = None
    creado: str
    # Correo del Administrador inicial del portal (nivel 3 más antiguo). `None` en el caso
    # límite de un portal sin ningún Administrador (no ocurre por el flujo de alta actual,
    # que siempre crea uno junto al portal).
    adminEmail: str | None = None


# --- Ajustes: campo [Empresa] -----------------------------------------------

class EmpresaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    empresa: str = Field(min_length=1)


class EmpresaOut(BaseModel):
    empresa: str


# --- Ajustes: marca visual (paleta + logo), solo Administrador --------------

# Color hexadecimal `#rgb` o `#rrggbb`. La validación de formato la hace Pydantic;
# la de contraste WCAG la hace el router con `app.contraste` (autoridad del servidor).
ColorHex = Annotated[str, Field(pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")]


class MarcaIn(BaseModel):
    """Paleta editable por Administrador: solo el acento.

    Las tres paradas del degradado del banner ya no son entrada: el servidor las deriva
    del acento (`derivar_degradado_banner`). `extra="ignore"` (por defecto) descarta sin
    error cualquier parada de banner que envíe un cliente antiguo o manipulado; el
    resultado guardado es siempre el derivado y validado, nunca el del cuerpo.
    """

    model_config = ConfigDict(extra="ignore")

    acento: ColorHex


class MarcaOut(BaseModel):
    acento: str
    bannerDesde: str
    bannerMedio: str
    bannerHasta: str


class LogoOut(BaseModel):
    """Estado del logotipo para el panel. Nunca incluye el binario."""

    presente: bool
    mime: str | None = None


# --- Ajustes: plantilla del centro de ayuda, solo Administrador --------------

class PlantillaIn(BaseModel):
    """Elección de plantilla del portal. Admitidas: las de `PLANTILLAS_ADMITIDAS`.

    El conjunto se declara una sola vez en `app/servicios.py` y lo consumen este
    esquema (422 aquí) y el normalizador de lectura; no se duplica como `Literal`
    para que añadir una plantilla no exija tocar dos sitios.
    """

    model_config = ConfigDict(extra="forbid")

    plantilla: str

    @field_validator("plantilla")
    @classmethod
    def _admitida(cls, valor: str) -> str:
        if valor not in PLANTILLAS_ADMITIDAS:
            raise ValueError(
                f"Plantilla no admitida: {valor!r}. "
                f"Admitidas: {', '.join(PLANTILLAS_ADMITIDAS)}."
            )
        return valor


class PlantillaOut(BaseModel):
    """Plantilla guardada, tal como la publica el contenido público."""

    plantilla: str


# --- Ajustes: enlace de GitHub del portal, solo Administrador ----------------

# Hosts admitidos. El icono se rotula «GitHub», así que el enlace solo puede llevar a
# GitHub: un Administrador no puede convertirlo en un enlace a un sitio cualquiera.
_HOSTS_GITHUB = ("github.com", "www.github.com")
GITHUB_URL_MAX = 300


class GithubIn(BaseModel):
    """URL del repositorio de GitHub del portal. Vacía o nula la borra (oculta el icono)."""

    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, max_length=GITHUB_URL_MAX)

    @field_validator("url")
    @classmethod
    def _solo_github(cls, valor: str | None) -> str | None:
        if valor is None or valor.strip() == "":
            return None
        valor = valor.strip()
        partes = urlsplit(valor)
        if (
            partes.scheme != "https"
            or (partes.hostname or "").lower() not in _HOSTS_GITHUB
            or partes.username is not None
            or partes.password is not None
            or partes.port is not None
        ):
            raise ValueError("La URL debe ser de GitHub y empezar por https://github.com/.")
        return valor


class GithubOut(BaseModel):
    """Enlace guardado (nulo si se borró)."""

    url: str | None


# --- Configuración de proveedor de IA (solo SuperAdmin) ---------------------

# Proveedores admitidos. Cada uno tiene motor real en algunos roles y no en otros:
# `anthropic` y `deepseek` tienen motor de traducción (Anthropic también sirve
# como motor recomendado por Claude, y DeepSeek además tiene motor de chat);
# `openai` y `voyage` (Voyage AI, adquirida por Anthropic en 2025) tienen motor
# de embeddings para el RAG. La correspondencia rol → proveedores viable la
# expone el backend en `rolesSoportados` (ver `RolesSoportadosOut`); el frontend
# filtra sus selectores con ese mapa. Google se retiró de la lista al separar
# roles: no tenía motor real en ninguno (ver cambio `separar-proveedores-ia`).
ProveedorIA = Literal["anthropic", "deepseek", "openai", "voyage"]


class ProveedorEstado(BaseModel):
    """Estado de un proveedor: si tiene clave configurada y una pista para
    identificarla (los últimos caracteres). NUNCA incluye la clave completa."""

    id: ProveedorIA
    configurada: bool
    # Últimos caracteres de la clave (p. ej. "s7xq") para que el Administrador reconozca cuál
    # está puesta, sin exponer el resto. `None` si no hay clave o es demasiado corta
    # para revelar sin descubrir casi toda la clave.
    pista: str | None = None


class RolesSoportadosOut(BaseModel):
    """Proveedores con motor real por rol de IA. El frontend usa este mapa para
    filtrar cada selector de la tarjeta de configuración; el backend rechaza con
    422 cualquier asignación de rol → proveedor fuera de la lista de ese rol."""

    chat: list[ProveedorIA]
    traduccion: list[ProveedorIA]
    embeddings: list[ProveedorIA]


class ConfigIAOut(BaseModel):
    """Configuración de IA para el panel: proveedor por rol y estado de las claves.
    NUNCA devuelve las claves en claro (solo el booleano `configurada` y una pista)."""

    # `None` en un rol significa «sin proveedor asignado»: la fábrica cae al
    # default codificado (ver `PROVEEDOR_*_POR_DEFECTO` en `servicios_ia.py`).
    proveedorChat: ProveedorIA | None = None
    proveedorTraduccion: ProveedorIA | None = None
    proveedorEmbeddings: ProveedorIA | None = None
    proveedores: list[ProveedorEstado]
    rolesSoportados: RolesSoportadosOut


class SaludRolOut(BaseModel):
    """Resultado del sondeo de un rol contra su proveedor.

    `detalle` lo redacta el backend (`app.salud_ia`); NUNCA es el texto crudo del
    proveedor, que puede llevar datos de cuenta o de infraestructura y va solo al log.
    """

    rol: Literal["chat", "traduccion", "embeddings"]
    proveedor: ProveedorIA
    # `credenciales` (clave revocada) y `saldo` (cuenta sin fondos) se separan a
    # propósito: los dos producen el mismo 502 en el panel pero se arreglan distinto.
    estado: Literal["ok", "sin_clave", "credenciales", "saldo", "timeout", "error"]
    detalle: str
    # ISO 8601, como el resto de marcas de tiempo del contrato (`creado_en`).
    comprobadoEn: str


class SaludIAOut(BaseModel):
    """Salud de los tres roles de IA, en el orden `chat`, `traduccion`, `embeddings`."""

    roles: list[SaludRolOut]


class ConfigIAIn(BaseModel):
    """Cambia el proveedor de uno o varios roles y, opcionalmente, la clave de un
    proveedor (o su borrado).

    - `proveedorX = None` significa «no cambiar ese rol»; `proveedorX = "..."` lo
      sobrescribe. El backend valida que el proveedor asignado pertenece a
      `rolesSoportados[rol]`; en otro caso responde 422.
    - `clave` no vacía → cifrar y guardar (upsert) bajo `proveedor` (obligatorio
      si viene `clave`). `clave` vacía/ausente = «no cambiar la clave».
    - `borrarClave=True` + `proveedor` → `DELETE` de esa fila de `config_ia_clave`.
      Si el proveedor está referenciado por algún rol (persistido o en el mismo
      cuerpo), el backend responde 409 con un detalle legible.
    """

    model_config = ConfigDict(extra="forbid")

    proveedorChat: ProveedorIA | None = None
    proveedorTraduccion: ProveedorIA | None = None
    proveedorEmbeddings: ProveedorIA | None = None

    proveedor: ProveedorIA | None = None
    clave: str | None = None
    borrarClave: bool = False


# --- RAG: gestión de documentos (solo Administrador) ------------------------

# Estado del ciclo de ingesta expuesto al panel. La transición la controla el
# servidor: `pendiente` → `procesando` → `listo` | `error`.
EstadoDocumento = Literal["pendiente", "procesando", "listo", "error"]

# Idioma del documento cargado. `ambos` (por defecto) indica que el contenido
# debe indexarse contra ambos idiomas de recuperación (es/pt).
IdiomaDocumento = Literal["es", "pt", "ambos"]


class DocumentoOut(BaseModel):
    """Documento devuelto por el panel: metadatos y estado de la ingesta.

    NUNCA incluye el binario (ya no existe: se descarta tras extraer texto) ni
    los embeddings (irrelevantes para el panel). Las fechas viajan como ISO 8601.
    """

    id: int
    nombre: str
    mime: str
    idioma: str
    estado: EstadoDocumento
    # `None` mientras el estado no es `error`; texto legible cuando falla la ingesta.
    errorDetalle: str | None = None
    # Tamaño del archivo original en bytes (para orientar al Administrador).
    bytes: int
    creado: str
    actualizado: str


# --- Traducción asistida por IA ---------------------------------------------

class TraduccionPeticionIn(BaseModel):
    """Pide traducir el contenido de un idioma al otro. No persiste nada."""

    model_config = ConfigDict(extra="forbid")

    origen: Idioma
    contenido: TraduccionArticuloIn


class TraduccionPeticionCategoriaIn(BaseModel):
    """Pide traducir el nombre de una categoría de un idioma al otro. No persiste
    nada; espejo de `TraduccionPeticionIn` acotado al contenido de categoría."""

    model_config = ConfigDict(extra="forbid")

    origen: Idioma
    contenido: TraduccionCategoriaIn


# --- Chat con RAG (endpoint público) ----------------------------------------

# Roles del historial que el cliente envía. `usuario` y `asistente` en lugar de
# `user`/`assistant` para mantener la nomenclatura del resto de la API.
#
# El input del cliente SOLO admite `usuario`. Aceptar `asistente` permitiría a un
# atacante inyectar un turno de "asistente anterior" que el LLM tiende a tratar
# como contexto autoritativo (fake-history prompt injection). El historial de
# asistente en la conversación devuelta al cliente (para el mailto de
# escalamiento) sigue existiendo, pero se serializa desde el server, no viene
# del cliente. Persistir historial server-side ligado a `session_id` queda para
# el cambio posterior `historial-chat-server`.
RolTurnoIn = Literal["usuario"]
RolTurno = Literal["usuario", "asistente"]

# Longitud máxima de un turno del historial que el cliente adjunta. Espeja
# `CHAT_MAX_CONSULTA_CHARS` (500) pero se declara aquí como cota estructural
# para cortar payloads antes de invocar al pipeline.
MAX_TURNO_CHARS = 500


class TurnoChatIn(BaseModel):
    """Turno del historial que el cliente adjunta a la consulta. Solo `usuario`."""

    model_config = ConfigDict(extra="forbid")

    rol: RolTurnoIn
    texto: str = Field(min_length=1, max_length=MAX_TURNO_CHARS)


class TurnoChat(BaseModel):
    """Turno serializado que devuelve el endpoint (conversación para escalamiento)."""

    model_config = ConfigDict(extra="forbid")

    rol: RolTurno
    texto: str = Field(min_length=1, max_length=MAX_TURNO_CHARS)


class FuenteChatOut(BaseModel):
    """Fuente citada en la respuesta del chat, para renderizar el bloque de fuentes."""

    n: int
    tipo: Literal["articulo", "documento"]
    titulo: str
    # `slug` está presente para artículos (permite construir el enlace en el
    # cliente vía `rutas.articulo(idioma, slug)`); vacío para documentos.
    slug: str = ""


VeredictoChat = Literal["respondida", "sin_resultados", "fuera_de_scope", "escalar"]
RazonEscalamientoChat = Literal[
    "solicitud_usuaria", "sin_resultados", "tope_turnos", "error_proveedor"
]


class ChatConsultaIn(BaseModel):
    """Entrada del endpoint público de chat. El `portal_id` NO se acepta: el
    servidor lo resuelve del host y cualquier valor que envíe el cliente se
    ignora silenciosamente (extra=`ignore`).

    Contrato renombrado: el campo canónico es `chat_id`. Durante un ciclo de
    transición se sigue aceptando `session_id` como alias entrante para no
    romper clientes en vuelo; si el cliente envía ambos, gana `chat_id` (el
    alias se descarta). El backend siempre devuelve `chat_id`.
    """

    model_config = ConfigDict(extra="ignore")

    # Longitud validada estructuralmente aquí y de nuevo en el pipeline (para
    # que la función `responder` sea autosuficiente en tests unitarios).
    consulta: str = Field(min_length=1, max_length=MAX_TURNO_CHARS)
    # `chat_id` opaco emitido por el servidor. `None` en la primera consulta.
    chat_id: str | None = None
    # Alias entrante durante la transición del rename `session_id` → `chat_id`.
    # No se emite nunca en la salida y `chat_id` tiene prioridad si vienen los dos.
    session_id: str | None = None
    # Historial que el cliente conserva localmente (el servidor no lo persiste).
    # Cotas estructurales: 50 turnos máx (el pipeline se queda con los últimos N).
    # Solo turnos de `usuario`: ver `TurnoChatIn`.
    historial: list[TurnoChatIn] = Field(default_factory=list, max_length=50)
    # Bandera de escalamiento explícito desde el widget ("contactar soporte").
    solicitar_soporte: bool = False

    @property
    def chat_id_efectivo(self) -> str | None:
        """`chat_id` si viene, `session_id` como alias, `None` si ninguno."""
        return self.chat_id or self.session_id


class ChatConsultaOut(BaseModel):
    """Salida del endpoint público de chat.

    `chat_id` viaja siempre (emitido o renovado). `fuentes` solo trae valores
    con `veredicto: respondida`. `razon` y `conversacion` solo con
    `veredicto: escalar`. `fuera_de_scope` no lleva ni fuentes ni conversación.
    """

    veredicto: VeredictoChat
    mensaje: str
    chat_id: str
    fuentes: list[FuenteChatOut] = Field(default_factory=list)
    razon: RazonEscalamientoChat | None = None
    conversacion: list[TurnoChat] = Field(default_factory=list)


# --- Panel: supervisión de chats (spec `supervision-chats`) -----------------

class ChatItemOut(BaseModel):
    """Fila agregada por `chat_id` para el listado del panel.

    Un chat es una conversación (varias interacciones con el mismo `chat_id`);
    la tabla del panel muestra una fila por chat, no por turno. `creado_en` es
    la fecha del primer turno y `ultima_en` la del último; `ultimo_veredicto`
    resume el estado en el que quedó el chat.
    """

    chat_id: str
    portal_id: str
    idioma: str
    turnos: int
    ultimo_veredicto: VeredictoChat
    creado_en: str
    ultima_en: str


class ChatListaOut(BaseModel):
    """Listado paginado de chats agregados por `chat_id`.

    `siguiente_cursor` es `None` cuando no hay más páginas; en caso contrario,
    el cliente lo reenvía como `?cursor=` en la siguiente petición. El formato
    interno del cursor es opaco (no lo interpreta el frontend).
    """

    items: list[ChatItemOut]
    siguiente_cursor: str | None = None


class ChatInteraccionOut(BaseModel):
    """Una interacción persistida en `chat_interaccion` (un turno del chat).

    Espeja los campos del modelo con `creado_en` serializado ISO 8601. Los
    campos que pueden ser NULL en la base viajan como `null` (razón de
    escalamiento salvo `veredicto=escalar`; tokens si el proveedor no los
    reporta).
    """

    id: str
    chat_id: str
    portal_id: str
    turno: int
    idioma: str
    consulta: str
    veredicto: VeredictoChat
    mensaje: str
    citas: list[dict[str, Any]]
    razon_escalamiento: str | None = None
    latencia_ms: int
    tokens_entrada: int | None = None
    tokens_salida: int | None = None
    proveedor: str
    modelo: str
    creado_en: str


class ChatDetalleOut(BaseModel):
    """Hilo completo de un chat: sus interacciones ordenadas por `turno`."""

    chat_id: str
    portal_id: str
    interacciones: list[ChatInteraccionOut]


# --- Panel: sugerencias de artículo con IA (spec `sugerencia-articulos-ia`) --

FuenteSugerencia = Literal["chat_escalado", "pregunta_sin_resolver", "documentacion_rag"]
EstadoSugerencia = Literal["pendiente", "aceptada", "descartada"]


class CandidatoOut(BaseModel):
    """Candidato a artículo agregado de una fuente, para la lista del panel."""

    fuente: FuenteSugerencia
    referencia: str
    titulo_sugerido: str
    idioma: str
    prioridad: int
    ya_generada: bool


class CandidatosListaOut(BaseModel):
    items: list[CandidatoOut]


class GenerarSugerenciaIn(BaseModel):
    """Candidato elegido para generar su borrador (`POST .../generar`)."""

    model_config = ConfigDict(extra="forbid")

    fuente: FuenteSugerencia
    referencia: str = Field(min_length=1, max_length=MAX_TEXTO_CORTO)


class CitaSugerenciaOut(BaseModel):
    n: int
    tipo: Literal["articulo", "documento"]
    titulo: str
    slug: str = ""


class SugerenciaOut(BaseModel):
    """Borrador completo, para el detalle que precarga el formulario de artículo."""

    id: str
    portal_id: str
    fuente: FuenteSugerencia
    referencia: str
    estado: EstadoSugerencia
    es: TraduccionArticuloIn
    pt: TraduccionArticuloIn
    citas: list[CitaSugerenciaOut]
    proveedor_chat: str
    proveedor_traduccion: str
    modelo: str
    articulo_id: str | None = None
    creado_por: str
    creado_en: str
    resuelto_en: str | None = None


class SugerenciaItemOut(BaseModel):
    """Fila de la cola de pendientes (sin el contenido bilingüe completo)."""

    id: str
    fuente: FuenteSugerencia
    referencia: str
    titulo: str
    estado: EstadoSugerencia
    creado_en: str


class SugerenciasListaOut(BaseModel):
    items: list[SugerenciaItemOut]


class ChatMetricasOut(BaseModel):
    """Métricas agregadas del chat para el rango consultado.

    - `chats_total`: cuántos `chat_id` distintos hubo en el periodo.
    - `chats_respondidos_con_cita_pct`: 0..100 (float, 2 decimales). Porcentaje
      de esos chats cuyo último veredicto es `respondida`.
    - `chats_escalados`: cuántos chats cerraron con `veredicto=escalar`.
    - `desde`/`hasta`: rango efectivo aplicado (útil cuando no llega en la
      petición y el servidor cae al default de los últimos 30 días).
    """

    chats_total: int
    chats_respondidos_con_cita_pct: float
    chats_escalados: int
    desde: str
    hasta: str
