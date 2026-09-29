'use client'

import type { ReactNode } from 'react'
import { usePathname } from 'next/navigation'
import type { ContenidoIdioma, Idioma } from '@/types'
import type { Tema } from '@/tema/tema'
import { resolverPlantilla, esRutaAdministracion } from '@/plantillas/plantillas'
import { AppHeader } from './AppHeader'
import { ArmazonDocumentacion } from './plantillas/documentacion/ArmazonDocumentacion'

/**
 * Cromo del sitio: elige entre el armazón de la plantilla de documentación y la cabecera
 * de siempre, según la plantilla del portal y la ruta.
 *
 * **La superficie de administración queda fuera de la plantilla.** `/{idioma}/panel*` y el
 * login conservan la cabecera actual aunque el portal use `documentacion`: la plantilla es
 * presentación del sitio público y el panel no cambia con ella (spec
 * `plantillas-centro-ayuda`). La decisión vive en un Client Component precisamente por eso:
 * `usePathname()` da la ruta también en servidor, así el HTML inicial ya sale con el cromo
 * correcto y no hay salto al hidratar.
 *
 * `children` son las páginas del servidor: se reciben ya renderizadas y llegan en el HTML
 * inicial igual que antes.
 */
export function CromoPorPlantilla({
  idioma,
  contenido,
  tema,
  children,
}: {
  idioma: Idioma
  contenido: ContenidoIdioma | null
  /** Preferencia de modo noche leída de la cookie; solo la aplica el armazón de documentación. */
  tema: Tema
  children: ReactNode
}) {
  const pathname = usePathname()
  const esAdministracion = esRutaAdministracion(pathname, idioma)

  if (
    contenido === null ||
    esAdministracion ||
    resolverPlantilla(contenido.plantilla) !== 'documentacion'
  ) {
    return (
      <>
        <AppHeader
          idioma={idioma}
          empresa={contenido?.empresa}
          logo={contenido?.logo}
          logoVersion={contenido?.logoVersion}
        />
        {children}
      </>
    )
  }

  return (
    <ArmazonDocumentacion idioma={idioma} contenido={contenido} temaInicial={tema}>
      {children}
    </ArmazonDocumentacion>
  )
}
