"""API pública de contenido: sirve el `ContenidoIdioma` por idioma."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import portal_actual
from app.models import Portal
from app.schemas import ContenidoIdiomaOut
from app.servicios import IDIOMAS, ensamblar_contenido

router = APIRouter(prefix="/api", tags=["contenido"])


@router.get(
    "/{idioma}/contenido",
    response_model=ContenidoIdiomaOut,
    response_model_exclude_none=True,
)
def obtener_contenido(
    idioma: str,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    if idioma not in IDIOMAS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Idioma no encontrado")
    # El contenido se acota al portal resuelto por el host: nunca se mezcla con otro.
    return ensamblar_contenido(db, idioma, portal.id)
