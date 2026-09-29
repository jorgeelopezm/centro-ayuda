"""Panel interno: preguntas sin resolver y creación de artículo desde una pregunta (ciclo KCS)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import portal_actual, requiere_nivel
from app.models import Articulo, NivelAcceso, Portal, PreguntaSinResolver
from app.routers.comun import exigir_id_disponible, validar_relacionados
from app.schemas import ArticuloAdminOut, ArticuloIn, PreguntaAdminOut
from app.servicios import aplicar_datos_articulo, articulo_a_admin_dict, pregunta_a_dict
from app.texto import normalizar_slug

# El panel de preguntas sin resolver es una función de producto: Nivel 2 o superior.
router = APIRouter(
    prefix="/api/admin/preguntas-sin-resolver",
    tags=["admin"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.EDITOR))],
)


@router.get("", response_model=list[PreguntaAdminOut])
def listar(
    idioma: str | None = None,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> list[dict]:
    consulta = db.query(PreguntaSinResolver).filter(PreguntaSinResolver.portal_id == portal.id)
    if idioma is not None:
        consulta = consulta.filter(PreguntaSinResolver.idioma == idioma)
    filas = consulta.order_by(PreguntaSinResolver.orden).all()
    return [pregunta_a_dict(p) for p in filas]


@router.post(
    "/{pregunta_id}/crear-articulo",
    response_model=ArticuloAdminOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_articulo_desde_pregunta(
    pregunta_id: int,
    datos: ArticuloIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    # La pregunta debe ser del portal del host: una de otro portal responde 404.
    pregunta = (
        db.query(PreguntaSinResolver)
        .filter(
            PreguntaSinResolver.id == pregunta_id,
            PreguntaSinResolver.portal_id == portal.id,
        )
        .first()
    )
    if pregunta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pregunta no encontrada")
    id_normalizado = normalizar_slug(datos.id)
    exigir_id_disponible(db, portal.id, id_normalizado)
    validar_relacionados(db, portal.id, id_normalizado, datos.relacionados)

    a = Articulo()
    aplicar_datos_articulo(a, datos, incluir_id=True, portal_id=portal.id)
    db.add(a)
    # Cierra el ciclo KCS: la pregunta queda cubierta por el nuevo artículo.
    pregunta.estado = "cubierta"
    db.commit()
    db.refresh(a)
    return articulo_a_admin_dict(a)
