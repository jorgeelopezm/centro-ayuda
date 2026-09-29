"""Gestión de usuarios, exclusiva de Administrador (Nivel 3).

Permite crear, editar y activar/desactivar usuarios y asignar su nivel. Las
salvaguardas viven aquí, en el servidor: nadie puede autodesactivarse ni
autodegradarse, ni dejar el sistema sin ningún Administrador activo.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import portal_actual, requiere_nivel
from app.models import AdminUser, NivelAcceso, Portal
from app.schemas import UsuarioActualizarIn, UsuarioCrearIn, UsuarioOut
from app.security import hash_password
from app.servicios import usuario_a_dict

router = APIRouter(
    prefix="/api/admin/usuarios",
    tags=["admin", "usuarios"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.ADMINISTRADOR))],
)


def _obtener_o_404(db: Session, portal_id: str, usuario_id: int) -> AdminUser:
    # Acotado al portal: un usuario de otro portal no existe para esta sesión (404).
    usuario = (
        db.query(AdminUser)
        .filter(AdminUser.id == usuario_id, AdminUser.portal_id == portal_id)
        .first()
    )
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return usuario


def _administradores_activos(db: Session, portal_id: str) -> int:
    # La salvaguarda del "último Administrador" es **por portal**: solo cuentan los
    # Administradores activos de este portal, no los de otros.
    return (
        db.query(AdminUser)
        .filter(
            AdminUser.portal_id == portal_id,
            AdminUser.nivel == NivelAcceso.ADMINISTRADOR,
            AdminUser.activo.is_(True),
        )
        .count()
    )


def _es_ultimo_administrador_activo(db: Session, usuario: AdminUser) -> bool:
    return (
        usuario.nivel == NivelAcceso.ADMINISTRADOR
        and usuario.activo
        and _administradores_activos(db, usuario.portal_id) <= 1
    )


@router.get("", response_model=list[UsuarioOut])
def listar(
    db: Session = Depends(get_db), portal: Portal = Depends(portal_actual)
) -> list[dict]:
    usuarios = (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == portal.id)
        .order_by(AdminUser.id)
        .all()
    )
    return [usuario_a_dict(u) for u in usuarios]


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: UsuarioCrearIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    # El correo es único **por portal**: se comprueba solo dentro de este portal.
    existe = (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == portal.id, AdminUser.email == datos.email)
        .first()
    )
    if existe is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")
    usuario = AdminUser(
        portal_id=portal.id,
        email=datos.email,
        password_hash=hash_password(datos.password),
        nivel=int(datos.nivel),
        activo=True,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario_a_dict(usuario)


@router.put("/{usuario_id}", response_model=UsuarioOut)
def actualizar(
    usuario_id: int,
    datos: UsuarioActualizarIn,
    db: Session = Depends(get_db),
    actual: AdminUser = Depends(requiere_nivel(NivelAcceso.ADMINISTRADOR)),
) -> dict:
    usuario = _obtener_o_404(db, actual.portal_id, usuario_id)
    degrada = int(datos.nivel) < NivelAcceso.ADMINISTRADOR

    # Nadie se degrada a sí mismo: perdería el propio acceso Administrador sin querer.
    if usuario.id == actual.id and degrada:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes quitarte tu propio nivel Administrador")
    # No dejar el portal sin ningún Administrador activo.
    if degrada and _es_ultimo_administrador_activo(db, usuario):
        raise HTTPException(status.HTTP_409_CONFLICT, "Debe quedar al menos un usuario Administrador activo")

    otro = (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == actual.portal_id, AdminUser.email == datos.email)
        .first()
    )
    if otro is not None and otro.id != usuario.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")

    usuario.email = datos.email
    usuario.nivel = int(datos.nivel)
    if datos.password is not None:
        usuario.password_hash = hash_password(datos.password)
    db.commit()
    db.refresh(usuario)
    return usuario_a_dict(usuario)


@router.post("/{usuario_id}/activar", response_model=UsuarioOut)
def activar(
    usuario_id: int,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> dict:
    usuario = _obtener_o_404(db, portal.id, usuario_id)
    usuario.activo = True
    db.commit()
    db.refresh(usuario)
    return usuario_a_dict(usuario)


@router.post("/{usuario_id}/desactivar", response_model=UsuarioOut)
def desactivar(
    usuario_id: int,
    db: Session = Depends(get_db),
    actual: AdminUser = Depends(requiere_nivel(NivelAcceso.ADMINISTRADOR)),
) -> dict:
    usuario = _obtener_o_404(db, actual.portal_id, usuario_id)
    # Nadie se desactiva a sí mismo: se cerraría el propio acceso.
    if usuario.id == actual.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes desactivar tu propia cuenta")
    # No dejar el sistema sin ningún Administrador activo.
    if _es_ultimo_administrador_activo(db, usuario):
        raise HTTPException(status.HTTP_409_CONFLICT, "Debe quedar al menos un usuario Administrador activo")
    usuario.activo = False
    db.commit()
    db.refresh(usuario)
    return usuario_a_dict(usuario)
