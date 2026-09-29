"""CRUD de categorías, protegido por sesión de administrador. Crear/editar exige es+pt.

Es una función de producto (gestión de contenido): la usa cualquier sesión válida
(Nivel 2, Editor, o superior), como el CRUD de artículos. El borrado se bloquea con
409 si la categoría todavía tiene artículos asignados (integridad referencial).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import portal_actual, requiere_nivel
from app.models import Categoria, NivelAcceso, Portal
from app.routers.comun import (
    exigir_categoria_id_disponible,
    exigir_categoria_sin_articulos,
    obtener_categoria_o_404,
)
from app.schemas import (
    CategoriaAdminOut,
    CategoriaIn,
    CategoriaUpdateIn,
    TraduccionCategoriaIn,
    TraduccionPeticionCategoriaIn,
)
from app.servicios import aplicar_datos_categoria, categoria_a_admin_dict
from app.servicios_ia import ProveedorTraduccion, obtener_traductor, traducir_contenido
from app.texto import normalizar_slug

router = APIRouter(
    prefix="/api/admin/categorias",
    tags=["admin"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.EDITOR))],
)


@router.get("", response_model=list[CategoriaAdminOut])
def listar(
    db: Session = Depends(get_db), portal: Portal = Depends(portal_actual)
) -> list[dict]:
    categorias = (
        db.query(Categoria)
        .filter(Categoria.portal_id == portal.id)
        .order_by(Categoria.orden)
        .all()
    )
    return [categoria_a_admin_dict(c) for c in categorias]


@router.get("/{categoria_id}", response_model=CategoriaAdminOut)
def obtener(
    categoria_id: str,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    return categoria_a_admin_dict(obtener_categoria_o_404(db, portal.id, categoria_id))


@router.post("/traducir", response_model=TraduccionCategoriaIn)
def traducir(
    datos: TraduccionPeticionCategoriaIn,
    traductor: ProveedorTraduccion = Depends(obtener_traductor),
) -> dict:
    """Traduce el nombre de una categoría de un idioma al otro con el proveedor
    configurado. No persiste nada: el frontend vuelca el resultado como borrador
    editable. Espejo de `admin_articulos.traducir`, acotado al contenido de
    categoría (sin párrafos, pasos ni FAQ que traducir_contenido pueda comparar).
    """
    return traducir_contenido(traductor, datos.origen, datos.contenido)


@router.post("", response_model=CategoriaAdminOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: CategoriaIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    # Se comprueba la disponibilidad con el id ya normalizado (el mismo que persiste).
    exigir_categoria_id_disponible(db, portal.id, normalizar_slug(datos.id))
    c = Categoria()
    aplicar_datos_categoria(c, datos, incluir_id=True, portal_id=portal.id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return categoria_a_admin_dict(c)


@router.put("/{categoria_id}", response_model=CategoriaAdminOut)
def actualizar(
    categoria_id: str,
    datos: CategoriaUpdateIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    c = obtener_categoria_o_404(db, portal.id, categoria_id)
    aplicar_datos_categoria(c, datos, incluir_id=False, portal_id=portal.id)
    db.commit()
    db.refresh(c)
    return categoria_a_admin_dict(c)


@router.delete("/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    categoria_id: str,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> None:
    c = obtener_categoria_o_404(db, portal.id, categoria_id)
    # Bloqueo con integridad referencial: no se borra si aún tiene artículos.
    exigir_categoria_sin_articulos(db, portal.id, categoria_id)
    # Sin artículos: se borra junto a sus traducciones (cascade all, delete-orphan).
    db.delete(c)
    db.commit()
