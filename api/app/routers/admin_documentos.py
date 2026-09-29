"""Gestión de documentos del índice RAG. Reservada a Administrador (Nivel 3).

Un documento es un archivo (PDF, DOCX, Markdown o TXT) que el Administrador
sube al portal. La API lo persiste como metadatos + fragmentos + embeddings; el
binario se descarta tras extraer texto (design.md D7 del cambio `rag-ingesta`).
Todo se acota al portal del host: un Administrador de otro portal no ve ni
alcanza los documentos de este (acceso por id directo → 404).

La subida usa **body binario crudo** con `Content-Disposition` para el nombre
de archivo, siguiendo el patrón del logotipo (`admin_ajustes.subir_logo`). Se
evita `python-multipart` como dependencia; el BFF de Next reenvía el body sin
transformarlo. El idioma del documento se pasa como query param.

La ingesta corre en `BackgroundTasks`: el POST responde 201 con el documento en
estado `procesando` y la ingesta continúa fuera de la petición. La interfaz
hace polling de `GET /api/admin/documentos/{id}` para reflejar el estado.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import portal_actual, requiere_nivel
from app.ingesta import ingerir_documento
from app.models import Documento, DocumentoChunk, NivelAcceso, Portal
from app.routers.comun import obtener_documento_o_404
from app.schemas import DocumentoOut
from app.servicios import documento_a_dict
from app.troceo import (
    MAX_BYTES_DOCUMENTO,
    ArchivoInvalido,
    FormatoNoAdmitido,
    validar_subida,
)

router = APIRouter(
    prefix="/api/admin/documentos",
    tags=["admin", "rag"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.ADMINISTRADOR))],
)

# Idiomas admitidos para el documento subido. `ambos` (por defecto) indica que
# el contenido debe indexarse contra ambos idiomas de recuperación (es/pt).
_IDIOMAS_ADMITIDOS = frozenset({"es", "pt", "ambos"})

# Regex para leer el `filename` de la cabecera `Content-Disposition` según
# RFC 6266. Se soporta tanto la forma tradicional `filename="..."` como la
# codificada `filename*=UTF-8''...`.
_RE_FILENAME_ASTERISCO = re.compile(
    r"""filename\*\s*=\s*(?:UTF-8|utf-8)''(?P<v>[^;]+)""",
    re.IGNORECASE,
)
_RE_FILENAME = re.compile(
    r"""filename\s*=\s*(?:"(?P<q>[^"]+)"|(?P<v>[^;]+))""",
    re.IGNORECASE,
)


def _extraer_nombre(request: Request) -> str:
    """Nombre de archivo desde `Content-Disposition`, con fallback a `documento`.

    Se prefiere `filename*=UTF-8''...` (RFC 5987) por soportar caracteres no
    ASCII; si no está, se cae a `filename="..."`. En última instancia se
    devuelve un nombre genérico para no dejar el documento sin etiqueta en el
    panel (el Administrador puede identificarlo por fecha si hace falta).
    """
    cd = request.headers.get("content-disposition") or ""
    m_ast = _RE_FILENAME_ASTERISCO.search(cd)
    if m_ast:
        return unquote(m_ast.group("v").strip()).strip()
    m = _RE_FILENAME.search(cd)
    if m:
        return (m.group("q") or m.group("v") or "").strip() or "documento"
    return "documento"


@router.get("", response_model=list[DocumentoOut])
def listar(
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> list[dict]:
    """Lista los documentos del portal, más nuevos primero (por id descendente)."""
    docs = (
        db.query(Documento)
        .filter(Documento.portal_id == portal.id)
        .order_by(Documento.id.desc())
        .all()
    )
    return [documento_a_dict(d) for d in docs]


@router.get("/{documento_id}", response_model=DocumentoOut)
def obtener(
    documento_id: int,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    """Estado/detalle de un documento del portal (endpoint de polling del panel)."""
    return documento_a_dict(obtener_documento_o_404(db, portal.id, documento_id))


@router.post("", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED)
async def subir(
    request: Request,
    background: BackgroundTasks,
    idioma: str = "ambos",
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    """Sube un documento (body binario crudo) y arranca la ingesta en background.

    El Content-Type declarado por el cliente identifica el formato (`validar_subida`
    normaliza los alias de Markdown al mime canónico). El nombre se lee de
    `Content-Disposition`. El idioma se valida como query param.

    Se responde 201 con el documento en estado `procesando`; el frontend
    consulta `GET /{id}` para ver la transición a `listo` o `error`.
    """
    if idioma not in _IDIOMAS_ADMITIDOS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Idioma no admitido: usa 'es', 'pt' o 'ambos'.",
        )
    mime_bruto = request.headers.get("content-type") or ""
    # `Content-Type` puede incluir parámetros (charset, boundary) tras `;`.
    mime = mime_bruto.split(";", 1)[0].strip().lower()

    datos = await request.body()
    try:
        mime_canonico = validar_subida(mime, len(datos))
    except FormatoNoAdmitido as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except ArchivoInvalido as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    documento = Documento(
        portal_id=portal.id,
        nombre=_extraer_nombre(request),
        mime=mime_canonico,
        idioma=idioma,
        estado="procesando",
        bytes=len(datos),
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)

    # La ingesta abre su propia sesión (la de la petición se cierra al terminar);
    # se le pasa el binario porque no se persiste en la base.
    background.add_task(ingerir_documento, documento.id, datos)
    return documento_a_dict(documento)


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    documento_id: int,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> Response:
    """Borra el documento y sus fragmentos.

    La FK `documento_chunks.documento_id` es `ON DELETE CASCADE`, así que
    borrar el documento arrastra los fragmentos en Postgres. Se hace también un
    delete explícito para que el requisito «sin huérfanos» sea observable
    también bajo SQLite (los tests corren allí, sin CASCADE efectivo en todas
    las versiones), y para acotar mejor el comportamiento del router.
    """
    documento = obtener_documento_o_404(db, portal.id, documento_id)
    (
        db.query(DocumentoChunk)
        .filter(DocumentoChunk.documento_id == documento.id)
        .delete(synchronize_session=False)
    )
    db.delete(documento)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
