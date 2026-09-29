"""Ajustes de marca **por portal**. Hoy: el campo [Empresa], la paleta y el logotipo,
editables por Administrador.

La lectura del nombre de marca es pública (viaja en `GET /api/{idioma}/contenido`);
aquí vive solo la escritura, reservada a Nivel 3 (Administrador). La escritura afecta
siempre a la fila de ajustes **del portal del host**, nunca a la de otro portal.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.contraste import derivar_degradado_banner, validar_paleta
from app.database import get_db
from app.deps import portal_actual, requiere_nivel
from app.imagenes import MAX_LOGO_BYTES, detectar_mime_logo
from app.models import Ajustes, NivelAcceso, Portal
from app.schemas import (
    EmpresaIn,
    EmpresaOut,
    GithubIn,
    GithubOut,
    LogoOut,
    MarcaIn,
    MarcaOut,
    PlantillaIn,
    PlantillaOut,
)
from app.servicios import fila_ajustes, normalizar_plantilla

router = APIRouter(
    prefix="/api/admin/ajustes",
    tags=["admin", "ajustes"],
    dependencies=[Depends(requiere_nivel(NivelAcceso.ADMINISTRADOR))],
)


def _fila_ajustes(db: Session, portal_id: str) -> Ajustes:
    """Fila de marca visual **del portal**, creándola si el seed aún no la creó.

    La fila es por portal (`portal_id` único) y su `id` lo autoincrementa la base, así
    que un portal distinto del `default` obtiene su propia fila de marca sin colisionar.
    """
    ajuste = fila_ajustes(db, portal_id)
    if ajuste is None:
        ajuste = Ajustes(portal_id=portal_id)
        db.add(ajuste)
    return ajuste


@router.put("/empresa", response_model=EmpresaOut)
def actualizar_empresa(
    datos: EmpresaIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> EmpresaOut:
    # El nombre de empresa es del portal (`Portal.nombre_empresa`), su fuente única; no
    # vive en los ajustes de marca. Se edita el del portal del host, nunca el de otro.
    portal.nombre_empresa = datos.empresa
    db.commit()
    return EmpresaOut(empresa=portal.nombre_empresa)


@router.put("/marca", response_model=MarcaOut)
def actualizar_marca(
    datos: MarcaIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> MarcaOut:
    """Guarda la paleta si cumple WCAG AA; si no, rechaza con 422 y no persiste.

    El Administrador elige solo el acento: el degradado del banner se **deriva** de él
    (`derivar_degradado_banner`), monocromático y accesible por construcción. El servidor
    es la autoridad —deriva aquí, no confía en paradas del cuerpo— y valida todos los
    pares (botón, hover, foco, cada parada derivada) antes de persistir. El frontend solo
    adelanta el aviso.
    """
    banner = derivar_degradado_banner(datos.acento)
    fallo = validar_paleta(datos.acento, banner["desde"], banner["medio"], banner["hasta"])
    if fallo is not None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "mensaje": f"Contraste insuficiente: {fallo.par}.",
                "par": fallo.par,
                "ratio": fallo.ratio,
                "minimo": fallo.minimo,
            },
        )
    ajuste = _fila_ajustes(db, portal.id)
    ajuste.acento = datos.acento
    ajuste.banner_desde = banner["desde"]
    ajuste.banner_medio = banner["medio"]
    ajuste.banner_hasta = banner["hasta"]
    db.commit()
    return MarcaOut(
        acento=ajuste.acento,
        bannerDesde=ajuste.banner_desde,
        bannerMedio=ajuste.banner_medio,
        bannerHasta=ajuste.banner_hasta,
    )


@router.put("/plantilla", response_model=PlantillaOut)
def actualizar_plantilla(
    datos: PlantillaIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> PlantillaOut:
    """Guarda la plantilla del sitio público **del portal del host**.

    Espejo de `/marca` y `/logo` (nivel Administrador, fila de ajustes del portal del
    host, creada si el seed no la creó). La respuesta devuelve el valor guardado
    normalizado, para que el panel confirme con la verdad del servidor y no con lo que
    creyó enviar. Un valor no admitido lo corta `PlantillaIn` con 422 antes de llegar
    aquí, así que la escritura nunca deja la columna con una plantilla inexistente.
    """
    ajuste = _fila_ajustes(db, portal.id)
    ajuste.plantilla = datos.plantilla
    db.commit()
    return PlantillaOut(plantilla=normalizar_plantilla(ajuste.plantilla))


@router.put("/github", response_model=GithubOut)
def actualizar_github(
    datos: GithubIn,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> GithubOut:
    """Guarda (o borra, con `url` vacía o nula) el enlace de GitHub **del portal del host**.

    Mismo patrón que `/plantilla`. `GithubIn` corta con 422 cualquier URL que no sea
    `https://github.com/…`, así que la columna nunca guarda un enlace a otro sitio.
    """
    ajuste = _fila_ajustes(db, portal.id)
    ajuste.github_url = datos.url
    db.commit()
    return GithubOut(url=ajuste.github_url)


@router.post("/logo", response_model=LogoOut, status_code=status.HTTP_201_CREATED)
async def subir_logo(
    request: Request,
    db: Session = Depends(get_db),
    portal: Portal = Depends(portal_actual),
) -> LogoOut:
    """Sube el logotipo (PNG/ICO/JPEG) como cuerpo binario crudo.

    Se recibe el binario directo (sin multipart) para no añadir `python-multipart`: el
    tipo se decide por magic bytes, no por el nombre de archivo, así que no hace falta
    el envoltorio de formulario. El BFF reenvía el cuerpo tal cual.
    """
    datos = await request.body()
    if len(datos) == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El archivo está vacío.")
    if len(datos) > MAX_LOGO_BYTES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"El logotipo supera el tamaño máximo ({MAX_LOGO_BYTES // 1024} KB).",
        )
    # El tipo se decide por el contenido, no por la extensión ni el Content-Type cliente.
    mime = detectar_mime_logo(datos)
    if mime is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Formato no admitido. Solo se aceptan PNG, ICO o JPEG (no SVG).",
        )
    ajuste = _fila_ajustes(db, portal.id)
    ajuste.logo_bin = datos
    ajuste.logo_mime = mime
    db.commit()
    return LogoOut(presente=True, mime=mime)
