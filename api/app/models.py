"""Modelos SQLAlchemy. Patrón bilingüe: entidad estable + traducciones por idioma.

Los campos anidados (`parrafos`, `how_to`, `faq`, `mensajes`) usan un tipo JSON portable:
JSONB en PostgreSQL (producción) y JSON en SQLite (tests en memoria).
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.rag import EMBEDDING_DIM

# JSONB en Postgres, JSON en el resto (permite testear en SQLite sin pgvector).
JsonType = JSON().with_variant(JSONB(), "postgresql")


def _vector_type():
    """Tipo de columna para embeddings.

    En Postgres es `pgvector.Vector(N)` (índice HNSW, distancia coseno). En
    SQLite (tests) cae a `JSON` para que los modelos se puedan importar sin la
    extensión: los tests no ejercitan distancia vectorial, solo lógica de
    troceo, estado y aislamiento por portal (con dobles del proveedor de
    embeddings). Espeja el patrón de `JsonType` con JSONB.
    """
    try:
        from pgvector.sqlalchemy import Vector
    except ImportError:  # pragma: no cover - dependencia opcional en el import de tests
        return JSON()
    # `Vector` va como tipo base (no como variante) para que su `Comparator`
    # exponga `cosine_distance` en el ORM: `with_variant` solo cambia el tipo
    # en la emisión de SQL/DDL, no el `Comparator` que se resuelve en el acceso
    # de atributos Python (`ArticuloChunk.embedding.cosine_distance(...)`).
    return Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")


VectorType = _vector_type()


class NivelAcceso(enum.IntEnum):
    """Niveles de acceso jerárquicos. El valor entero ordena la herencia de
    permisos: autorizar es comparar `nivel_actual >= nivel_requerido`.

    ANONIMO nunca se persiste (es la ausencia de sesión); EDITOR y ADMINISTRADOR
    viven como `nivel` en `admin_users` acotados a su portal. SUPERADMIN es
    transversal (gestiona portales): no se ata a un portal de contenido sino al
    portal de plataforma reservado (ver `PORTAL_PLATAFORMA_SLUG`). Los valores 1–3
    no cambian, por compatibilidad de API con el modelo single-tenant.
    """

    ANONIMO = 1
    EDITOR = 2
    ADMINISTRADOR = 3
    SUPERADMIN = 4


class Portal(Base):
    """Tenant. Unidad de aislamiento: cada artículo, categoría, usuario, pregunta sin
    resolver y ajuste de marca pertenece a exactamente un portal (`portal_id`).

    `id` es un UUID opaco (clave estable referenciada por las FKs), separado del
    `slug`, la clave legible que define el subdominio `<slug>.tuapp.com`. Separar
    identidad de nombre público deja el `slug` libre para hacerse editable en el
    futuro sin cascadear un cambio de PK por las ~15 tablas con FK `portal_id`
    (migración `0012_portal_uuid`). `estado` permite suspender un portal sin
    borrarlo ("activo"/"suspendido"). `nombre_empresa` es el valor de marca del
    portal (el campo interno `[Empresa]`), aquí por portal en lugar de global.
    """

    __tablename__ = "portales"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    nombre_empresa: Mapped[str] = mapped_column(String, nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False, default="activo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dominios: Mapped[list[Dominio]] = relationship(
        back_populates="portal", cascade="all, delete-orphan"
    )


class Dominio(Base):
    """Mapa `host → portal`. El subdominio del portal es la fila base; los dominios
    propios del cliente son filas adicionales que apuntan al mismo `portal_id`.

    La resolución del portal en el servidor busca el `Host` de la petición aquí. El
    modelo queda preparado para dominios propios (fase posterior de infraestructura:
    TLS/DNS por dominio); aquí solo se persiste el mapeo.
    """

    __tablename__ = "dominios"

    host: Mapped[str] = mapped_column(String, primary_key=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Marca el host canónico del portal (su subdominio), frente a los dominios propios.
    principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    portal: Mapped[Portal] = relationship(back_populates="dominios")


class Categoria(Base):
    __tablename__ = "categorias"
    # PK compuesta `(portal_id, id)`: el id de categoría es único *por portal*, no
    # global, igual que el slug. Así dos portales pueden reusar el mismo id sin
    # colisionar. Simétrico con `conversaciones`/`metricas`, cuya PK también lleva portal.
    __table_args__ = (PrimaryKeyConstraint("portal_id", "id"),)

    id: Mapped[str] = mapped_column(String)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    # Nulo = «sin icono» (migración `0016`): la categoría se muestra solo con su nombre.
    icono: Mapped[str | None] = mapped_column(String, nullable=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    traducciones: Mapped[list[CategoriaTraduccion]] = relationship(
        back_populates="categoria", cascade="all, delete-orphan"
    )


class CategoriaTraduccion(Base):
    __tablename__ = "categoria_traducciones"
    # Slug único por portal e idioma: dos portales pueden reusar el mismo slug de
    # categoría sin colisionar. `portal_id` se denormaliza desde la categoría padre
    # para poder imponer esa unicidad en la base.
    __table_args__ = (
        # La PK lleva `portal_id`: el id de categoría ya no es único global, así que
        # `(categoria_id, idioma)` podía chocar entre portales.
        PrimaryKeyConstraint("portal_id", "categoria_id", "idioma"),
        # FK compuesta a la PK por portal de la categoría (sustituye a la simple a
        # `categorias.id`): la traducción vive en el mismo portal que su categoría.
        ForeignKeyConstraint(
            ["portal_id", "categoria_id"],
            ["categorias.portal_id", "categorias.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("portal_id", "idioma", "slug", name="uq_categoria_trad_portal_slug"),
    )

    categoria_id: Mapped[str] = mapped_column(String)
    idioma: Mapped[str] = mapped_column(String)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String)
    nombre: Mapped[str] = mapped_column(String)

    categoria: Mapped[Categoria] = relationship(back_populates="traducciones")


class Articulo(Base):
    __tablename__ = "articulos"
    __table_args__ = (
        # PK compuesta `(portal_id, id)`: el id de artículo es único *por portal*, no
        # global. Cierra el que dos portales chocasen (o se enumerasen) por un mismo id.
        PrimaryKeyConstraint("portal_id", "id"),
        # La categoría del artículo es del mismo portal: FK compuesta a su PK por portal.
        ForeignKeyConstraint(
            ["portal_id", "categoria_id"], ["categorias.portal_id", "categorias.id"]
        ),
    )

    id: Mapped[str] = mapped_column(String)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    categoria_id: Mapped[str] = mapped_column(String)
    actualizado: Mapped[date] = mapped_column(Date)
    minutos_lectura: Mapped[int] = mapped_column(Integer)
    destacado: Mapped[bool] = mapped_column(Boolean, default=False)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    traducciones: Mapped[list[ArticuloTraduccion]] = relationship(
        back_populates="articulo", cascade="all, delete-orphan"
    )
    relacionados: Mapped[list[ArticuloRelacionado]] = relationship(
        back_populates="articulo",
        cascade="all, delete-orphan",
        order_by="ArticuloRelacionado.orden",
        # `articulo_relacionados` tiene dos FKs compuestas a `articulos` (articulo_id y
        # relacionado_id): se fija por cuál va esta relación de "enlaces salientes".
        primaryjoin=(
            "and_(Articulo.portal_id == ArticuloRelacionado.portal_id, "
            "Articulo.id == ArticuloRelacionado.articulo_id)"
        ),
        foreign_keys="[ArticuloRelacionado.portal_id, ArticuloRelacionado.articulo_id]",
    )


class ArticuloTraduccion(Base):
    __tablename__ = "articulo_traducciones"
    # Slug único por portal e idioma (misma lógica que en categorías): permite reusar
    # el mismo slug de artículo en portales distintos sin colisionar.
    __table_args__ = (
        # La PK lleva `portal_id`: el id de artículo ya no es único global, así que
        # `(articulo_id, idioma)` podía chocar entre portales.
        PrimaryKeyConstraint("portal_id", "articulo_id", "idioma"),
        # FK compuesta a la PK por portal del artículo (sustituye a la simple a
        # `articulos.id`): la traducción vive en el mismo portal que su artículo.
        ForeignKeyConstraint(
            ["portal_id", "articulo_id"],
            ["articulos.portal_id", "articulos.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("portal_id", "idioma", "slug", name="uq_articulo_trad_portal_slug"),
    )

    articulo_id: Mapped[str] = mapped_column(String)
    idioma: Mapped[str] = mapped_column(String)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String)
    titulo: Mapped[str] = mapped_column(String)
    parrafos: Mapped[list] = mapped_column(JsonType)
    how_to: Mapped[dict] = mapped_column(JsonType)
    nota: Mapped[str | None] = mapped_column(String, nullable=True)
    faq: Mapped[list] = mapped_column(JsonType)

    articulo: Mapped[Articulo] = relationship(back_populates="traducciones")


class ArticuloRelacionado(Base):
    __tablename__ = "articulo_relacionados"
    __table_args__ = (
        # Los dos extremos del enlace son del mismo portal: un único `portal_id`
        # participa en ambas FKs compuestas a `articulos`, así que el enlace no puede
        # cruzar de portal. La del origen es inmediata.
        ForeignKeyConstraint(
            ["portal_id", "articulo_id"],
            ["articulos.portal_id", "articulos.id"],
            ondelete="CASCADE",
        ),
        # La del destino es diferible: al borrar un artículo se limpian los enlaces que
        # lo apuntan (ON DELETE CASCADE), y las referencias mutuas/ciclos del seed
        # funcionan porque la comprobación se aplaza al commit (todas las filas ya están).
        ForeignKeyConstraint(
            ["portal_id", "relacionado_id"],
            ["articulos.portal_id", "articulos.id"],
            ondelete="CASCADE",
            deferrable=True,
            initially="DEFERRED",
        ),
    )

    portal_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    articulo_id: Mapped[str] = mapped_column(String, primary_key=True)
    relacionado_id: Mapped[str] = mapped_column(String, primary_key=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    articulo: Mapped[Articulo] = relationship(
        back_populates="relacionados",
        primaryjoin=(
            "and_(Articulo.portal_id == ArticuloRelacionado.portal_id, "
            "Articulo.id == ArticuloRelacionado.articulo_id)"
        ),
        foreign_keys="[ArticuloRelacionado.portal_id, ArticuloRelacionado.articulo_id]",
    )


class PreguntaSinResolver(Base):
    __tablename__ = "preguntas_sin_resolver"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    idioma: Mapped[str] = mapped_column(String)
    pregunta: Mapped[str] = mapped_column(String)
    veces: Mapped[int] = mapped_column(Integer)
    similitud: Mapped[float] = mapped_column(Float)
    fecha: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String)
    orden: Mapped[int] = mapped_column(Integer, default=0)


class Conversacion(Base):
    __tablename__ = "conversaciones"

    # Clave por portal e idioma: cada portal tiene su propia conversación de ejemplo.
    portal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portales.id"), primary_key=True)
    idioma: Mapped[str] = mapped_column(String, primary_key=True)
    mensajes: Mapped[list] = mapped_column(JsonType)


class Metrica(Base):
    __tablename__ = "metricas"

    # Clave por portal, idioma y métrica: las métricas del panel son por portal.
    portal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portales.id"), primary_key=True)
    idioma: Mapped[str] = mapped_column(String, primary_key=True)
    clave: Mapped[str] = mapped_column(String, primary_key=True)
    valor: Mapped[str] = mapped_column(String)
    orden: Mapped[int] = mapped_column(Integer, default=0)


class AdminUser(Base):
    __tablename__ = "admin_users"
    # El correo es único por portal, no globalmente: dos portales pueden tener cada
    # uno un `admin@ejemplo.com`. El SuperAdmin (nivel 4, transversal) se modela en el
    # cambio de niveles de acceso; aquí `portal_id` es obligatorio para Editor y
    # Administrador (acotados a su portal).
    __table_args__ = (
        UniqueConstraint("portal_id", "email", name="uq_admin_users_portal_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    # Nivel de acceso: 2 (Editor) o 3 (Administrador). Se guarda el entero de NivelAcceso.
    nivel: Mapped[int] = mapped_column(Integer, nullable=False, default=NivelAcceso.EDITOR.value)
    # Permite revocar el acceso sin borrar la fila (conserva la traza).
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshToken(Base):
    """Refresh token opaco de sesión, guardado **hasheado** (nunca en claro).

    Modelo de rotación con detección de reutilización: cada renovación consume el
    token (`usado=True`) y emite otro dentro de la misma `familia`. Si se presenta
    un token ya consumido (replay tras robo), se revoca la familia entera. El
    `logout` revoca la familia. La autoridad de la sesión sigue en la base: un
    usuario desactivado no puede renovar (se comprueba en `app.sesiones`).
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("admin_users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Cadena de rotación: todos los tokens emitidos por renovación comparten familia.
    familia: Mapped[str] = mapped_column(String, index=True, nullable=False)
    # SHA-256 del valor opaco. Único: identifica el token sin guardarlo en claro.
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    emitido: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expira: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Consumido por una renovación: volver a presentarlo es reutilización.
    usado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Invalidado (logout o revocación de familia por reutilización).
    revocado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Ajustes(Base):
    """Marca **visual** por portal (una fila por `portal_id`).

    Guarda el color de acento, las tres paradas del degradado del banner de inicio y el
    logotipo (binario + MIME). Los colores llevan por defecto el aspecto índigo actual;
    el logo es opcional (sin logo, la cabecera cae al recuadro de iniciales y el favicon
    al de por defecto). Cada portal tiene su propia fila (`portal_id` único); el portal
    `default` conserva la fila histórica (`id=1`).

    El **nombre de empresa** (valor de `[Empresa]`) NO vive aquí: su fuente única es
    `Portal.nombre_empresa` (cada portal muestra el suyo, ver spec `gestion-portales`).
    """

    __tablename__ = "ajustes"

    # `id` autoincremental: cada portal tiene su propia fila. La clave real por la que
    # se busca es `portal_id` (único); el `id` es solo la PK técnica. Antes llevaba
    # `default=1` (era singleton), lo que forzaba `id=1` en cada inserción y hacía
    # colisionar la fila de un segundo portal; se quita para que la base autoincremente.
    # El portal `default` conserva su fila histórica `id=1` (sembrada explícitamente).
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, unique=True
    )
    # Colores hex `#rrggbb`. Los valores por defecto reproducen el aspecto actual.
    acento: Mapped[str] = mapped_column(String, nullable=False, default="#4338ca")
    banner_desde: Mapped[str] = mapped_column(String, nullable=False, default="#3730a3")
    banner_medio: Mapped[str] = mapped_column(String, nullable=False, default="#4338ca")
    banner_hasta: Mapped[str] = mapped_column(String, nullable=False, default="#4f46e5")
    # Plantilla del sitio público del portal: `default` (diseño actual) o
    # `documentacion` (armazón de documentación). Vive aquí por ser presentación del
    # portal, igual que el acento o el logo. El conjunto admitido, la plantilla por
    # defecto y el normalizador de lectura viven en `app/servicios.py` (fuente única);
    # aquí el literal solo reproduce el `server_default` de la migración `0015`.
    plantilla: Mapped[str] = mapped_column(
        String, nullable=False, default="default", server_default="default"
    )
    # URL del repositorio de GitHub del portal. Nula = sin enlace: la plantilla de
    # documentación oculta el icono. La valida `GithubIn` (solo https://github.com/…).
    github_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Logotipo subido (PNG/ICO). Nulo mientras no se suba ninguno.
    logo_bin: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    logo_mime: Mapped[str | None] = mapped_column(String, nullable=True)


class Documento(Base):
    """Documento subido para el índice RAG.

    Guarda **solo metadatos**: nombre, mime, idioma declarado, estado de la
    ingesta y bytes del original (para diagnóstico y auditoría). El binario se
    **descarta** tras extraer texto (ver design.md D7); si más adelante se
    quisiera re-trocear sin re-subir, habría que persistirlo (patrón `marca.py`).

    `portal_id` es obligatorio: el aislamiento por tenant se aplica al RAG
    igual que al resto. La PK es entero autoincremental (el patrón de
    `admin_users`/`preguntas_sin_resolver`): el id no tiene semántica de
    negocio, así que no vale la pena hacerlo compuesto con portal.
    """

    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    mime: Mapped[str] = mapped_column(String, nullable=False)
    # `es`, `pt` o `ambos`. Se usará al filtrar por idioma en la recuperación
    # futura; por defecto `ambos` (indexa contra ambos idiomas de artículos).
    idioma: Mapped[str] = mapped_column(String, nullable=False, default="ambos")
    # Ciclo: `pendiente` (recién creado) → `procesando` (extrayendo/embebiendo)
    # → `listo` (todos los fragmentos indexados) | `error`. Si la ingesta falla
    # la transacción hace rollback: no quedan fragmentos parciales del doc.
    estado: Mapped[str] = mapped_column(String, nullable=False, default="pendiente")
    error_detalle: Mapped[str | None] = mapped_column(String, nullable=True)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    fragmentos: Mapped[list[DocumentoChunk]] = relationship(
        back_populates="documento", cascade="all, delete-orphan"
    )


class DocumentoChunk(Base):
    """Fragmento de texto de un `Documento` con su embedding.

    `ON DELETE CASCADE` desde el documento: borrar el documento arrastra sus
    fragmentos y sus embeddings (se cumple el requisito «sin huérfanos»).
    `portal_id` denormalizado desde el padre para acotar consultas por tenant
    sin joins.
    """

    __tablename__ = "documento_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    documento_id: Mapped[int] = mapped_column(
        ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    # `Vector(EMBEDDING_DIM)` en Postgres, JSON en SQLite (tests). El índice
    # HNSW vive en la migración; el modelo no lo declara.
    embedding: Mapped[list[float]] = mapped_column(VectorType, nullable=False)

    documento: Mapped[Documento] = relationship(back_populates="fragmentos")


class ArticuloChunk(Base):
    """Fragmento de texto de un `Articulo` por idioma con su embedding.

    Los artículos son bilingües (es/pt); el troceo produce una fila por idioma
    y fragmento. La FK es **compuesta** hacia la PK por portal de `articulos`
    (`(portal_id, articulo_id) → articulos(portal_id, id)`), no simple, porque
    `articulos.pk = (portal_id, id)` desde la migración multi-tenant `0006`.
    `ON DELETE CASCADE` cierra el requisito «al borrar un artículo, sus
    fragmentos también».
    """

    __tablename__ = "articulo_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["portal_id", "articulo_id"],
            ["articulos.portal_id", "articulos.id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id"), nullable=False, index=True
    )
    articulo_id: Mapped[str] = mapped_column(String, nullable=False)
    # `es` | `pt`. Cada artículo tiene ambas traducciones (paridad obligatoria).
    idioma: Mapped[str] = mapped_column(String, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VectorType, nullable=False)


class ConfigIA(Base):
    """Configuración de IA. Fila única (`id=1`), editable solo por SuperAdmin.

    Un campo escalar por **rol** de IA (chat, traducción, embeddings): cada rol se
    resuelve por separado, sin acoplarse a un único «proveedor activo» compartido.
    Los tres son `NULL` por defecto; cuando lo son, la fábrica de ese rol cae al
    default codificado (ver `PROVEEDOR_*_POR_DEFECTO` en `servicios_ia.py`). Las
    claves de API viven en la tabla `config_ia_clave` (una fila por proveedor),
    NO aquí (ver cambio OpenSpec `separar-proveedores-ia`).

    Es un singleton **global a la instalación** (sin `portal_id`): la misma config
    vale para todos los portales, así que la gestiona el SuperAdmin transversal, no
    el Administrador de un portal (evita que el admin de un tenant pise la clave o
    el proveedor que usan los demás; ver `routers/admin_config_ia.py`).
    """

    __tablename__ = "config_ia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Un campo escalar por rol. `NULL` = «sin configurar»: la fábrica del rol cae
    # a su default codificado. SuperAdmin puede cambiar cada rol de forma
    # independiente por el panel.
    proveedor_chat: Mapped[str | None] = mapped_column(String, nullable=True)
    proveedor_traduccion: Mapped[str | None] = mapped_column(String, nullable=True)
    proveedor_embeddings: Mapped[str | None] = mapped_column(String, nullable=True)
    # Modelo y temperatura del chat del centro de ayuda (RAG). Nullable a propósito:
    # `None` deja que el pipeline caiga a los valores por defecto (`deepseek-chat`, 0.2)
    # sin tocar la fila. SuperAdmin podrá editar estos campos desde el panel en un
    # cambio posterior; por ahora se leen aquí y se escriben con SQL/seed.
    modelo_chat: Mapped[str | None] = mapped_column(String, nullable=True)
    temperatura_chat: Mapped[float | None] = mapped_column(Float, nullable=True)


class ChatInteraccion(Base):
    """Una fila por turno del chat con RAG: la traza de la conversación que un
    Editor o Administrador podrá auditar desde el panel (spec `supervision-chats`).

    La PK es un UUID por interacción (no por chat): el `chat_id` es opaco (alias
    del `session_id` del pipeline) y se repite por cada turno; el `turno` es
    1-based dentro del `chat_id`. `citas` guarda una lista de `{n, tipo, titulo,
    slug}` (JSONB en Postgres, JSON en SQLite). `latencia_ms`, `tokens_entrada`,
    `tokens_salida`, `proveedor` y `modelo` sirven al harness de eval y al
    diagnóstico; los tokens pueden venir a NULL cuando el proveedor no los
    reporta. `razon_escalamiento` es NULL salvo con `veredicto=escalar`.

    Índices declarados en la migración `0011_chat_interaccion`:
    `(portal_id, creado_en desc)` para el listado agregado del panel y
    `(chat_id)` para el detalle.
    """

    __tablename__ = "chat_interaccion"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chat_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    turno: Mapped[int] = mapped_column(Integer, nullable=False)
    idioma: Mapped[str] = mapped_column(String, nullable=False)
    consulta: Mapped[str] = mapped_column(Text, nullable=False)
    veredicto: Mapped[str] = mapped_column(String, nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    # Lista de citas `[{n, tipo, titulo, slug}]`. Vacía para veredictos distintos
    # de `respondida`. JSONB en Postgres, JSON en SQLite (mismo patrón que en el
    # resto del modelo).
    citas: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    razon_escalamiento: Mapped[str | None] = mapped_column(String, nullable=True)
    latencia_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_salida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proveedor: Mapped[str] = mapped_column(String, nullable=False)
    modelo: Mapped[str] = mapped_column(String, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SugerenciaArticulo(Base):
    """Borrador de artículo generado por IA a partir de una señal (chat escalado,
    pregunta sin resolver o hueco de documentación RAG), pendiente de revisión
    humana (spec `sugerencia-articulos-ia`).

    `contenido` guarda `{"es": {...}, "pt": {...}}` con la misma forma que
    consume el formulario de artículo (`TraduccionArticuloIn`: slug, titulo,
    parrafos, howTo, nota, faq); NO incluye id/categoria/relacionados —esos los
    decide la persona editora al aceptar. `citas` es una lista de
    `{n, tipo, titulo, slug}` (mismo shape que `ChatInteraccion.citas`),
    fragmentos/artículos que sustentan el borrador, ya cruzados contra el
    portal. `articulo_id` queda `NULL` hasta que se acepta; entonces guarda el
    id del artículo real creado por el alta existente. `(fuente, referencia)`
    identifica el candidato de origen: sirve para no regenerar mientras exista
    una sugerencia `pendiente` para el mismo candidato (idempotencia).

    Nunca se publica ni se indexa por sí sola: mientras el estado sea
    `pendiente` o `descartada`, el contenido no aparece en el centro de ayuda
    público ni en el chat/RAG (no hay ningún router de lectura pública que
    consulte esta tabla).
    """

    __tablename__ = "sugerencia_articulo"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("portales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # `chat_escalado` | `pregunta_sin_resolver` | `documentacion_rag`.
    fuente: Mapped[str] = mapped_column(String, nullable=False)
    # Identificador estable del candidato dentro de su fuente (ver `app.sugerencias`).
    referencia: Mapped[str] = mapped_column(String, nullable=False)
    # `pendiente` | `aceptada` | `descartada`.
    estado: Mapped[str] = mapped_column(String, nullable=False, default="pendiente")
    contenido: Mapped[dict] = mapped_column(JsonType, nullable=False)
    citas: Mapped[list] = mapped_column(JsonType, nullable=False, default=list)
    proveedor_chat: Mapped[str] = mapped_column(String, nullable=False)
    proveedor_traduccion: Mapped[str] = mapped_column(String, nullable=False)
    modelo: Mapped[str] = mapped_column(String, nullable=False)
    # Id del artículo creado al aceptar. Sin FK a `articulos` (PK compuesta por
    # portal): la referencia es informativa, no de integridad; el artículo real
    # es la fuente de la verdad tras aceptar, y borrar la sugerencia después no
    # debe arrastrar al artículo (ni viceversa).
    articulo_id: Mapped[str | None] = mapped_column(String, nullable=True)
    creado_por: Mapped[str] = mapped_column(String, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resuelto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfigIAClave(Base):
    """Clave de API cifrada de un proveedor. Global a la instalación (no por portal).

    Una fila por proveedor (`proveedor` es la PK). `token_cifrado` guarda el token
    cifrado con Fernet (ver `app.cifrado`); NUNCA se guarda en claro ni se expone al
    cliente. `actualizado_en` refleja la última rotación de la clave.

    Sustituye al dict JSONB `ConfigIA.claves` de versiones anteriores: al ser tabla,
    cada fila queda tipada, `UNIQUE(proveedor)` se aplica en SQL, y borrar la clave de
    un proveedor es un `DELETE` limpio por PK sin tocar las demás.
    """

    __tablename__ = "config_ia_clave"

    proveedor: Mapped[str] = mapped_column(String, primary_key=True)
    token_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
