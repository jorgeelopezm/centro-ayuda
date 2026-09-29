"""Endpoints de sugerencias de artículo generadas por IA (spec `sugerencia-articulos-ia`).

Seis rutas, todas con nivel ≥ Editor y filtradas por el `portal_id` resuelto
del host:

- `GET /candidatos` — candidatos agregados de las tres fuentes (o una, con
  `?fuente=`).
- `POST /generar` — genera el borrador bilingüe de un candidato (idempotente
  mientras exista una sugerencia `pendiente` para el mismo `(fuente,
  referencia)`).
- `GET ""` — cola de sugerencias `pendiente`, más recientes primero.
- `GET /{id}` — detalle bilingüe con sus citas (precarga el formulario).
- `POST /{id}/aceptar` — crea el artículo real por el alta existente
  (bilingüe atómico + re-indexado) con el contenido editado por la persona
  revisora; marca la sugerencia `aceptada`.
- `POST /{id}/descartar` — marca `descartada` sin publicar nada.

Acceso cruzado por id → 404 (mismo criterio que `admin_chats`: no distingue
"no existe" de "no es de este portal"). `POST .../aceptar` reutiliza
`ArticuloIn`: un contenido incompleto (falta `es` o `pt`) lo rechaza Pydantic
con 422 antes de llegar aquí, así que la sugerencia queda `pendiente`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import admin_actual, portal_actual, requiere_nivel
from app.ingesta import reindexar_articulo
from app.models import AdminUser, Articulo, NivelAcceso, Portal, SugerenciaArticulo
from app.routers.comun import exigir_id_disponible, validar_relacionados
from app.schemas import (
    ArticuloAdminOut,
    ArticuloIn,
    CandidatosListaOut,
    FuenteSugerencia,
    GenerarSugerenciaIn,
    SugerenciaOut,
    SugerenciasListaOut,
)
from app.servicios import aplicar_datos_articulo, articulo_a_admin_dict
from app.sugerencias import ErrorGeneracionSugerencia, generar_borrador, listar_candidatos, resolver_candidato
from app.texto import normalizar_slug

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/sugerencias",
    tags=["admin", "sugerencias"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.EDITOR))],
)


def _sugerencia_o_404(db: Session, portal_id: uuid.UUID, sugerencia_id: str) -> SugerenciaArticulo:
    """Devuelve la sugerencia **del portal** o corta con 404 (aislamiento por
    portal, mismo criterio que `obtener_articulo_o_404`)."""
    try:
        sid = uuid.UUID(sugerencia_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sugerencia no encontrada") from exc
    s = (
        db.query(SugerenciaArticulo)
        .filter(SugerenciaArticulo.id == sid, SugerenciaArticulo.portal_id == portal_id)
        .first()
    )
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sugerencia no encontrada")
    return s


def _sugerencia_a_dict(s: SugerenciaArticulo) -> dict:
    contenido = s.contenido or {}
    return {
        "id": str(s.id),
        "portal_id": str(s.portal_id),
        "fuente": s.fuente,
        "referencia": s.referencia,
        "estado": s.estado,
        "es": contenido.get("es") or {},
        "pt": contenido.get("pt") or {},
        "citas": list(s.citas or []),
        "proveedor_chat": s.proveedor_chat,
        "proveedor_traduccion": s.proveedor_traduccion,
        "modelo": s.modelo,
        "articulo_id": s.articulo_id,
        "creado_por": s.creado_por,
        "creado_en": s.creado_en.isoformat() if s.creado_en is not None else "",
        "resuelto_en": s.resuelto_en.isoformat() if s.resuelto_en is not None else None,
    }


# --- Candidatos ---------------------------------------------------------------


@router.get("/candidatos", response_model=CandidatosListaOut)
def candidatos(
    fuente: FuenteSugerencia | None = Query(default=None),
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    items = listar_candidatos(db, portal.id, fuente)
    return {
        "items": [
            {
                "fuente": c.fuente,
                "referencia": c.referencia,
                "titulo_sugerido": c.titulo_sugerido,
                "idioma": c.idioma,
                "prioridad": c.prioridad,
                "ya_generada": c.ya_generada,
            }
            for c in items
        ]
    }


# --- Generación -----------------------------------------------------------


@router.post("/generar", response_model=SugerenciaOut, status_code=status.HTTP_201_CREATED)
def generar(
    datos: GenerarSugerenciaIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
    admin: AdminUser = Depends(admin_actual),
) -> dict:
    # Idempotencia: una sugerencia `pendiente` para el mismo candidato se
    # devuelve tal cual en lugar de gastar IA en regenerarla (design.md D2).
    existente = (
        db.query(SugerenciaArticulo)
        .filter(
            SugerenciaArticulo.portal_id == portal.id,
            SugerenciaArticulo.fuente == datos.fuente,
            SugerenciaArticulo.referencia == datos.referencia,
            SugerenciaArticulo.estado == "pendiente",
        )
        .first()
    )
    if existente is not None:
        return _sugerencia_a_dict(existente)

    candidato = resolver_candidato(db, portal.id, datos.fuente, datos.referencia)
    if candidato is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidato no encontrado")

    try:
        sugerencia = generar_borrador(candidato, str(portal.id), admin.email, db)
    except ErrorGeneracionSugerencia as exc:
        # Distinto del 502 de `ErrorProveedor` (main.py): aquí el proveedor SÍ
        # respondió, pero su salida no valida contra `_BorradorModelo`. Se registra
        # para poder separar ambas causas en el log sin depender del cuerpo HTTP.
        logger.warning(
            "Sugerencia descartada por forma inválida (portal=%s fuente=%s referencia=%s): %s",
            portal.id,
            candidato.fuente,
            candidato.referencia,
            exc,
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    return _sugerencia_a_dict(sugerencia)


# --- Cola de pendientes y detalle -------------------------------------------


@router.get("", response_model=SugerenciasListaOut)
def listar(
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    filas = (
        db.query(SugerenciaArticulo)
        .filter(SugerenciaArticulo.portal_id == portal.id, SugerenciaArticulo.estado == "pendiente")
        .order_by(SugerenciaArticulo.creado_en.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": str(s.id),
                "fuente": s.fuente,
                "referencia": s.referencia,
                "titulo": ((s.contenido or {}).get("es") or {}).get("titulo", ""),
                "estado": s.estado,
                "creado_en": s.creado_en.isoformat() if s.creado_en is not None else "",
            }
            for s in filas
        ]
    }


@router.get("/{sugerencia_id}", response_model=SugerenciaOut)
def detalle(
    sugerencia_id: str,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    return _sugerencia_a_dict(_sugerencia_o_404(db, portal.id, sugerencia_id))


# --- Aceptar / descartar -----------------------------------------------------


@router.post(
    "/{sugerencia_id}/aceptar", response_model=ArticuloAdminOut, status_code=status.HTTP_201_CREATED
)
def aceptar(
    sugerencia_id: str,
    datos: ArticuloIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    """Crea el artículo con el contenido **editado** por la persona revisora
    (no forzosamente el texto original de la IA) por el mismo alta que "Nuevo
    artículo": bilingüe atómico, choque de id → 409, re-indexado en segundo
    plano. Una sugerencia ya resuelta (`aceptada`/`descartada`) responde 409.
    """
    sugerencia = _sugerencia_o_404(db, portal.id, sugerencia_id)
    if sugerencia.estado != "pendiente":
        raise HTTPException(status.HTTP_409_CONFLICT, "La sugerencia ya fue resuelta")

    id_normalizado = normalizar_slug(datos.id)
    exigir_id_disponible(db, portal.id, id_normalizado)
    validar_relacionados(db, portal.id, id_normalizado, datos.relacionados)

    a = Articulo()
    aplicar_datos_articulo(a, datos, incluir_id=True, portal_id=portal.id)
    db.add(a)
    sugerencia.estado = "aceptada"
    sugerencia.articulo_id = id_normalizado
    sugerencia.resuelto_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(a)
    background.add_task(reindexar_articulo, portal.id, a.id)
    return articulo_a_admin_dict(a)


@router.post("/{sugerencia_id}/descartar", response_model=SugerenciaOut)
def descartar(
    sugerencia_id: str,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    sugerencia = _sugerencia_o_404(db, portal.id, sugerencia_id)
    if sugerencia.estado != "pendiente":
        raise HTTPException(status.HTTP_409_CONFLICT, "La sugerencia ya fue resuelta")
    sugerencia.estado = "descartada"
    sugerencia.resuelto_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(sugerencia)
    return _sugerencia_a_dict(sugerencia)
