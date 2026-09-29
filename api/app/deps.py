"""Dependencias de FastAPI.

`portal_actual` resuelve el portal de la petición a partir del host (la única fuente
del portal, nunca el cliente). `admin_actual` exige una sesión válida de un usuario
activo (Nivel 2 o superior) **de ese portal**. `requiere_nivel(minimo)` la envuelve
para exigir además un nivel mínimo, aplicando la jerarquía de acceso en el servidor.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AdminUser, NivelAcceso, Portal
from app.portales import normalizar_host, resolver_portal
from app.security import decodificar_token

_bearer = HTTPBearer(auto_error=False)


def _host_de_confianza(request: Request) -> str:
    """Host desde el que se resuelve el portal, tomado del proxy de confianza.

    El frontend de Next (proxy inmediato del backend) reenvía el host del navegador en
    `X-Forwarded-Host`; se prefiere sobre `Host`, que undici deriva de la URL interna del
    backend (`127.0.0.1:8000`) y no identificaría ningún portal. Si no llega reenviado
    (llamada directa, como en los tests), se cae al `Host`. Se toma solo el primer valor
    de la lista `X-Forwarded-Host` (el del cliente, no los saltos intermedios).

    `X-Forwarded-Host` solo se acepta cuando el peer inmediato está en
    `proxies_confiables`: un cliente que llegue directo al puerto del backend
    (bypassing el proxy) no puede suplantar el portal fabricando esa cabecera.
    Los tests que llaman al `TestClient` de Starlette ven `request.client=None`
    y caen al `Host`, así el aislamiento del test se mantiene igual.
    """
    if _peer_confiable(request):
        reenviado = request.headers.get("x-forwarded-host")
        bruto = reenviado.split(",", 1)[0] if reenviado else request.headers.get("host")
    else:
        bruto = request.headers.get("host")
    return normalizar_host(bruto)


def _peer_confiable(request: Request) -> bool:
    """`True` si el salto inmediato ante el backend está en `proxies_confiables`.

    Cuando FastAPI se accede por `TestClient` (`request.client is None`) se
    permite: los tests son entorno confiable y llaman a la app en proceso; no
    hay red que suplantar. En Windows y con uvicorn dual-stack, un cliente
    IPv4 puede llegar como IPv4-mapeada-en-IPv6 (`::ffff:127.0.0.1`); se
    normaliza para que el peer confiable no dependa de la representación.
    """
    if request.client is None:
        return True
    peer = request.client.host
    if peer.startswith("::ffff:"):
        peer = peer[len("::ffff:") :]
    return peer in get_settings().proxies_confiables_set


def portal_actual(request: Request, db: Session = Depends(get_db)) -> Portal:
    """Portal de la petición, resuelto en el servidor a partir del host.

    El host es la ÚNICA fuente del portal: nunca se toma de un parámetro, cabecera de
    aplicación o cuerpo del cliente (ver spec `resolucion-portal-por-dominio`). Un host
    desconocido responde 404 (portal no encontrado) y un portal suspendido 503 (portal
    no disponible), sin servir jamás datos de otro portal ni de un portal por defecto.
    """
    host = _host_de_confianza(request)
    portal = resolver_portal(db, host, base_domain=get_settings().base_domain)
    if portal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Portal no encontrado")
    if portal.estado != "activo":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Portal no disponible")
    return portal


def admin_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> AdminUser:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")
    datos = decodificar_token(cred.credentials)
    if datos is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")
    # La sesión se acota al portal del host: el token se emitió para un portal concreto
    # y solo vale en él. Como el correo es único por portal (no global), un token del
    # portal A presentado en el host del portal B —donde puede existir el mismo correo—
    # se rechaza aquí, antes de tocar la base, en vez de autenticar al homónimo de B.
    # `str(...)`: `portal.id` es un `uuid.UUID` (columna `Uuid`); `datos.portal_id` es
    # el `str` que trae el JWT (ver `crear_token`).
    if datos.portal_id != str(portal.id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida")
    admin = (
        db.query(AdminUser)
        .filter(AdminUser.portal_id == portal.id, AdminUser.email == datos.email)
        .first()
    )
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida")
    # Un usuario desactivado tiene el mismo acceso que uno sin sesión: la
    # comprobación se hace en cada petición (no en el token), así revocar el
    # acceso surte efecto de inmediato aunque el JWT siga sin expirar.
    if not admin.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida")
    return admin


def requiere_nivel(minimo: NivelAcceso) -> Callable[..., AdminUser]:
    """Fábrica de dependencias: exige que la sesión tenga al menos `minimo`.

    La jerarquía es un entero ordenado, así que Administrador (3) satisface cualquier
    requisito de Editor (2). Nivel insuficiente responde 403 (autenticado pero
    sin permiso), distinto del 401 de `admin_actual` (sin sesión válida).
    """

    def dependencia(admin: AdminUser = Depends(admin_actual)) -> AdminUser:
        if admin.nivel < minimo:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado para este recurso")
        return admin

    return dependencia
