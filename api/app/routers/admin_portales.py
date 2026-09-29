"""Gestión de portales, exclusiva del SuperAdmin (Nivel 4).

El SuperAdmin es transversal a la plataforma: crea, suspende y reactiva portales y
designa el Administrador de cada uno. Es el ÚNICO router que opera sobre **todos** los
portales a la vez (no se acota a `portal_actual`), porque su cometido es gestionar la
plataforma entera; la autorización `requiere_nivel(SUPERADMIN)` lo blinda en el servidor.

El propio SuperAdmin llega hasta aquí por el host de gestión del portal de plataforma
(`admin.<base_domain>`), que sí resuelve `portal_actual`; el slug `platform` está reservado
y no se sirve como portal de contenido, así que se excluye de la gestión (no se lista ni se
puede suspender: evita que el SuperAdmin se cierre su propia puerta).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import requiere_nivel
from app.models import AdminUser, Ajustes, Dominio, NivelAcceso, Portal
from app.portales import SLUGS_RESERVADOS
from app.schemas import PortalCrearIn, PortalOut
from app.security import hash_password
from app.servicios import PORTAL_PLATAFORMA_SLUG

router = APIRouter(
    prefix="/api/admin/portales",
    tags=["admin", "portales"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.SUPERADMIN))],
)


def _host_principal(db: Session, portal_id: uuid.UUID) -> str | None:
    dominio = (
        db.query(Dominio)
        .filter(Dominio.portal_id == portal_id, Dominio.principal.is_(True))
        .first()
    )
    return dominio.host if dominio is not None else None


def _admin_email(db: Session, portal_id: uuid.UUID) -> str | None:
    """Correo del Administrador inicial del portal: el de nivel 3 más antiguo.

    El alta (`crear`) siempre crea uno junto al portal; `None` es el caso límite de un
    portal sin ninguno (p. ej. si se desactivara después). Nunca expone el hash.
    """
    admin = (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == portal_id, AdminUser.nivel == NivelAcceso.ADMINISTRADOR.value)
        .order_by(AdminUser.created_at, AdminUser.id)
        .first()
    )
    return admin.email if admin is not None else None


def _portal_a_dict(db: Session, portal: Portal) -> dict:
    return {
        # `str(...)`: el id es un UUID de Python (`Portal.id: Mapped[uuid.UUID]`); se
        # serializa explícito en vez de confiar en la coacción implícita de Pydantic.
        "id": str(portal.id),
        "slug": portal.slug,
        "nombreEmpresa": portal.nombre_empresa,
        "estado": portal.estado,
        "host": _host_principal(db, portal.id),
        "creado": portal.created_at.isoformat() if portal.created_at is not None else "",
        "adminEmail": _admin_email(db, portal.id),
    }


def _obtener_o_404(db: Session, portal_id: str) -> Portal:
    # `portal_id` llega crudo de la URL (str): un valor que no sea un UUID válido no
    # puede ser el id de ningún portal, así que es 404 (no encontrado), no un 500 por
    # fallar la conversión al tipo de la columna más abajo.
    try:
        id_uuid = uuid.UUID(portal_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portal no encontrado") from None
    portal = db.get(Portal, id_uuid)
    # El portal de plataforma no es un portal de contenido gestionable: se oculta (404)
    # para que no se pueda suspender ni tocar desde esta superficie (autoprotección del
    # SuperAdmin, que entra por su host).
    if portal is None or portal.slug == PORTAL_PLATAFORMA_SLUG:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portal no encontrado")
    return portal


@router.get("", response_model=list[PortalOut])
def listar(db: Session = Depends(get_db)) -> list[dict]:
    # Todos los portales de contenido (el de plataforma se excluye: no es gestionable).
    portales = (
        db.query(Portal)
        .filter(Portal.slug != PORTAL_PLATAFORMA_SLUG)
        .order_by(Portal.created_at, Portal.id)
        .all()
    )
    return [_portal_a_dict(db, p) for p in portales]


@router.post("", response_model=PortalOut, status_code=status.HTTP_201_CREATED)
def crear(datos: PortalCrearIn, db: Session = Depends(get_db)) -> dict:
    slug = datos.slug
    # El formato del slug ya lo validó el esquema (Pydantic 422). Aquí, las reglas que
    # necesitan la base o la lista de reservas, que son autoridad del servidor.
    if slug in SLUGS_RESERVADOS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese slug está reservado")
    if db.query(Portal).filter(Portal.slug == slug).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un portal con ese slug")

    host = f"{slug}.{get_settings().base_domain}"
    if db.query(Dominio).filter(Dominio.host == host).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un portal con ese host")

    # El id es un UUID opaco que genera el default del modelo (`uuid.uuid4`), separado
    # del slug (clave legible, mutable en el futuro). `db.flush()` lo puebla en `portal.id`.
    portal = Portal(slug=slug, nombre_empresa=datos.nombreEmpresa, estado="activo")
    db.add(portal)
    # Fija el INSERT del portal antes que sus filas dependientes: las FKs `portal_id` lo
    # exigen (autoflush está desactivado en la sesión).
    db.flush()
    db.add(Dominio(host=host, portal_id=portal.id, principal=True))
    # Fila de marca visual por defecto (acento/banner índigo, sin logo); su `id` lo
    # autoincrementa la base.
    db.add(Ajustes(portal_id=portal.id))
    # El Administrador inicial del portal (nivel 3), acotado a él. El correo es único
    # por portal, así que puede reusarse el mismo en portales distintos.
    db.add(
        AdminUser(
            portal_id=portal.id,
            email=datos.adminEmail,
            password_hash=hash_password(datos.adminPassword),
            nivel=NivelAcceso.ADMINISTRADOR.value,
            activo=True,
        )
    )
    db.commit()
    db.refresh(portal)
    return _portal_a_dict(db, portal)


@router.post("/{portal_id}/suspender", response_model=PortalOut)
def suspender(portal_id: str, db: Session = Depends(get_db)) -> dict:
    # Suspender no borra nada: deja el contenido y los usuarios del portal inaccesibles
    # (`portal_actual` responde 503 y el login queda vetado) hasta reactivarlo.
    portal = _obtener_o_404(db, portal_id)
    portal.estado = "suspendido"
    db.commit()
    db.refresh(portal)
    return _portal_a_dict(db, portal)


@router.post("/{portal_id}/reactivar", response_model=PortalOut)
def reactivar(portal_id: str, db: Session = Depends(get_db)) -> dict:
    portal = _obtener_o_404(db, portal_id)
    portal.estado = "activo"
    db.commit()
    db.refresh(portal)
    return _portal_a_dict(db, portal)
