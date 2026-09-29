"""Punto de entrada de la API del Centro de Ayuda."""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.routers import (
    admin_ajustes,
    admin_articulos,
    admin_categorias,
    admin_chats,
    admin_config_ia,
    admin_documentos,
    admin_panel,
    admin_portales,
    admin_sugerencias,
    admin_usuarios,
    auth,
    chat,
    contenido,
    marca,
)
from app.servicios_ia import ErrorProveedor, ProveedorNoConfigurado

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Centro de Ayuda API",
    description="Contenido bilingüe, CRUD de artículos y autenticación del panel interno.",
    version="0.1.0",
)

app.include_router(contenido.router)
app.include_router(marca.router)
app.include_router(auth.router)
app.include_router(admin_articulos.router)
app.include_router(admin_categorias.router)
app.include_router(admin_panel.router)
app.include_router(admin_usuarios.router)
app.include_router(admin_portales.router)
app.include_router(admin_ajustes.router)
app.include_router(admin_config_ia.router)
app.include_router(admin_documentos.router)
app.include_router(admin_chats.router)
app.include_router(admin_sugerencias.router)
app.include_router(chat.router)


def _codigo_correlacion() -> str:
    """Identificador corto que aparece a la vez en el log del servidor y en el cuerpo
    de la respuesta. Permite que quien ve el error en el panel cite un código y que
    quien lee el log encuentre la línea exacta, sin exponer al navegador el texto
    crudo del proveedor (que puede llevar detalles de cuenta, cuota o infraestructura)."""
    return uuid.uuid4().hex[:8]


# Errores de traducción -> HTTP. Se registran a nivel de app para que el mapeo valga
# tanto si el error se lanza al resolver el proveedor (dependencia) como al traducir.
@app.exception_handler(ProveedorNoConfigurado)
def _sin_proveedor(request: Request, exc: ProveedorNoConfigurado) -> JSONResponse:
    # 409: el estado del servidor (sin proveedor/clave) impide traducir; el frontend
    # lo distingue para pedir a un usuario Administrador que configure el proveedor.
    codigo = _codigo_correlacion()
    logger.warning(
        "IA sin proveedor [%s] en %s: %s: %s",
        codigo,
        request.url.path,
        type(exc).__name__,
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "detail": "No hay proveedor de IA configurado. Un usuario Administrador debe configurarlo.",
            "codigo": codigo,
        },
    )


@app.exception_handler(ErrorProveedor)
def _error_proveedor(request: Request, exc: ErrorProveedor) -> JSONResponse:
    # El texto real del proveedor (p. ej. "402 Insufficient Balance", "401
    # Authentication Fails", "APITimeoutError") viaja dentro de `exc`: es la ÚNICA
    # copia que existe, porque quien lo lanza lo envuelve en `ErrorProveedor(str(exc))`
    # y no lo registra. Sin este log, un fallo del proveedor es indistinguible de un
    # bug propio desde fuera. Al cliente se le sigue dando un mensaje genérico.
    codigo = _codigo_correlacion()
    logger.warning(
        "Fallo del proveedor de IA [%s] en %s: %s: %s",
        codigo,
        request.url.path,
        type(exc).__name__,
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            # Neutral a propósito: este manejador cubre traducción, redacción de
            # borradores y embeddings. Decir "traducción" siempre despistaba el
            # diagnóstico cuando lo que había fallado era otra etapa.
            "detail": "El proveedor de IA no pudo completar la operación. Inténtalo de nuevo.",
            "codigo": codigo,
        },
    )


@app.exception_handler(IntegrityError)
def _error_integridad(_: Request, __: IntegrityError) -> JSONResponse:
    # Red de seguridad: una violación de integridad (p. ej. un relacionado que dejó
    # de existir entre la validación y el commit) es un dato inválido, no un fallo
    # del servidor. Se responde 422 en vez de dejar que se propague como 500.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "La operación viola una restricción de integridad de los datos."},
    )


@app.get("/api/salud", tags=["salud"])
def salud() -> dict:
    return {"estado": "ok"}
