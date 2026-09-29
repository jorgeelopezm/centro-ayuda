"""CRUD de artículos, protegido por sesión de administrador. Crear/editar exige es+pt."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import portal_actual, requiere_nivel
from app.ingesta import borrar_fragmentos_articulo, reindexar_articulo
from app.models import Articulo, NivelAcceso, Portal
from app.routers.comun import exigir_id_disponible, obtener_articulo_o_404, validar_relacionados
from app.schemas import (
    ArticuloAdminOut,
    ArticuloIn,
    ArticuloUpdateIn,
    TraduccionArticuloIn,
    TraduccionPeticionIn,
)
from app.servicios import aplicar_datos_articulo, articulo_a_admin_dict
from app.servicios_ia import ProveedorTraduccion, obtener_traductor, traducir_contenido
from app.texto import normalizar_slug

# El CRUD de artículos es una función de producto: la usa cualquier sesión válida
# (Nivel 2, Editor, o superior).
router = APIRouter(
    prefix="/api/admin/articulos",
    tags=["admin"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.EDITOR))],
)


@router.get("", response_model=list[ArticuloAdminOut])
def listar(
    db: Session = Depends(get_db), portal: Portal = Depends(portal_actual)
) -> list[dict]:
    articulos = (
        db.query(Articulo)
        .filter(Articulo.portal_id == portal.id)
        .order_by(Articulo.orden)
        .all()
    )
    return [articulo_a_admin_dict(a) for a in articulos]


@router.get("/{articulo_id}", response_model=ArticuloAdminOut)
def obtener(
    articulo_id: str,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    return articulo_a_admin_dict(obtener_articulo_o_404(db, portal.id, articulo_id))


@router.post("/traducir", response_model=TraduccionArticuloIn)
def traducir(
    datos: TraduccionPeticionIn,
    traductor: ProveedorTraduccion = Depends(obtener_traductor),
) -> dict:
    """Traduce el contenido de un idioma al otro con el proveedor configurado.

    No persiste nada: el frontend vuelca el resultado como borrador editable. Los
    errores del proveedor (sin configurar, fallo/límite) los mapean a HTTP los
    manejadores de `ErrorTraduccion` en `app.main`, tanto si se lanzan al resolver
    el proveedor (dependencia) como al traducir.
    """
    return traducir_contenido(traductor, datos.origen, datos.contenido)


@router.post("", response_model=ArticuloAdminOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: ArticuloIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    # Se comprueba la disponibilidad con el id ya normalizado (el mismo que persiste).
    id_normalizado = normalizar_slug(datos.id)
    exigir_id_disponible(db, portal.id, id_normalizado)
    validar_relacionados(db, portal.id, id_normalizado, datos.relacionados)
    a = Articulo()
    aplicar_datos_articulo(a, datos, incluir_id=True, portal_id=portal.id)
    db.add(a)
    db.commit()
    db.refresh(a)
    # Re-embedido en background: no penaliza la latencia de guardar. Si la
    # clave de OpenAI no está configurada, la ingesta lo registra y no rompe
    # la escritura del artículo (design.md D5/D8 del cambio `rag-ingesta`).
    background.add_task(reindexar_articulo, portal.id, a.id)
    return articulo_a_admin_dict(a)


@router.put("/{articulo_id}", response_model=ArticuloAdminOut)
def actualizar(
    articulo_id: str,
    datos: ArticuloUpdateIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    a = obtener_articulo_o_404(db, portal.id, articulo_id)
    validar_relacionados(db, portal.id, articulo_id, datos.relacionados)
    aplicar_datos_articulo(a, datos, incluir_id=False, portal_id=portal.id)
    db.commit()
    db.refresh(a)
    background.add_task(reindexar_articulo, portal.id, a.id)
    return articulo_a_admin_dict(a)


@router.delete("/{articulo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    articulo_id: str,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> None:
    # Borrado explícito de fragmentos antes de la fila del artículo: cierra
    # el requisito «sin huérfanos» incluso donde `ON DELETE CASCADE` no aplique
    # (p. ej. SQLite sin PRAGMA), y lo hace observable en tests.
    borrar_fragmentos_articulo(portal.id, articulo_id)
    db.delete(obtener_articulo_o_404(db, portal.id, articulo_id))
    db.commit()
