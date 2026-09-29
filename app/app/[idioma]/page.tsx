import { esIdioma } from '@/types'
import { redirect } from 'next/navigation'
import { traducir } from '@/i18n/traducir'
import { cargarContenidoServidor } from '@/data/servidor'
import { resolverPlantilla } from '@/plantillas/plantillas'
import { BuscadorAyuda } from '../_componentes/BuscadorAyuda'
import { EscalacionBloque } from '../_componentes/EscalacionBloque'
import { InicioDocumentacion } from '../_componentes/plantillas/documentacion/InicioDocumentacion'
import { PieDocumentacion } from '../_componentes/plantillas/documentacion/PieDocumentacion'

/**
 * Inicio del Centro de Ayuda. Server Component: el contenido (categorías y
 * populares) llega renderizado en el HTML inicial. La búsqueda es una isla de
 * cliente que se prerenderiza igualmente.
 *
 * Con la plantilla `documentacion` el contenido del inicio es el índice de la base de
 * conocimiento (`InicioDocumentacion`) y la búsqueda vive en la cabecera del armazón; con
 * `default` se conserva exactamente el inicio actual (`BuscadorAyuda`).
 */
export default async function PaginaInicio({ params }: { params: Promise<{ idioma: string }> }) {
  const { idioma } = await params
  if (!esIdioma(idioma)) redirect('/es')

  const t = traducir(idioma)
  const contenido = await cargarContenidoServidor(idioma)
  const esDocumentacion = resolverPlantilla(contenido.plantilla) === 'documentacion'

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="focus:outline-none"
      aria-label={t('inicio.titulo', { empresa: contenido.empresa })}
    >
      {esDocumentacion ? (
        <InicioDocumentacion idioma={idioma} contenido={contenido} />
      ) : (
        <BuscadorAyuda idioma={idioma} contenido={contenido} />
      )}

      {/* La escalación a soporte se mantiene con las dos plantillas: es función, no
          presentación. El ancho acompaña a la columna de cada armazón. */}
      <div
        className={`mx-auto px-4 sm:px-6 pb-16 pt-4 ${
          esDocumentacion ? 'max-w-4xl box-content lg:px-12' : 'max-w-5xl'
        }`}
      >
        <EscalacionBloque idioma={idioma} />
        {esDocumentacion && <PieDocumentacion idioma={idioma} />}
      </div>
    </main>
  )
}
