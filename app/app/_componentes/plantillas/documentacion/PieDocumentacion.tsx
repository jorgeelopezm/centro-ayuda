import Link from 'next/link'
import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { FECHA_LARGA, fechaLegible } from '@/i18n/fechas'
import { Ic } from '@/components/iconos'

/**
 * Pie de la plantilla de documentación: última actualización (cuando la página la tiene,
 * como el artículo) y accesos de ayuda. Server Component: solo texto y enlaces.
 *
 * Cierra la columna de contenido, como en la referencia. Los elementos de la referencia sin
 * origen de datos («editar esta página», incidencias, versión) quedan fuera de alcance
 * (ver `proposal.md`), así que los accesos son los que el portal sí puede servir: volver al
 * inicio y saltar al buscador de la cabecera.
 */
export function PieDocumentacion({
  idioma,
  actualizado,
}: {
  idioma: Idioma
  /** Fecha ISO (AAAA-MM-DD) del artículo, si la página la conoce. */
  actualizado?: string
}) {
  const t = traducir(idioma)
  const enlace =
    'inline-flex items-center gap-1.5 text-slate-600 hover:text-[var(--acento)] min-h-[44px] rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1'

  return (
    <footer className="mt-16 pt-8 border-t border-slate-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-sm text-slate-500">
      {actualizado ? (
        <p className="m-0">
          {t('plantillaDocumentacion.pie.ultimaActualizacion', {
            fecha: fechaLegible(actualizado, idioma, FECHA_LARGA),
          })}
        </p>
      ) : (
        <span aria-hidden="true" />
      )}
      <nav aria-label={t('plantillaDocumentacion.pie.etiqueta')}>
        <ul className="flex flex-wrap items-center gap-4 list-none p-0 m-0">
          <li>
            <Link href={rutas.inicio(idioma)} className={enlace}>
              <Ic.ArrowLeft size={15} className="shrink-0" />
              {t('plantillaDocumentacion.pie.volverInicio')}
            </Link>
          </li>
          <li>
            <Link href="#buscar-documentacion" className={enlace}>
              <Ic.Search size={15} className="shrink-0" />
              {t('plantillaDocumentacion.pie.buscar')}
            </Link>
          </li>
        </ul>
      </nav>
    </footer>
  )
}
