import Link from 'next/link'
import { notFound, redirect } from 'next/navigation'
import { esIdioma } from '@/types'
import { articuloPorId, articuloPorSlug } from '@/data'
import { cargarContenidoServidor } from '@/data/servidor'
import { traducir } from '@/i18n/traducir'
import { FECHA_LARGA, fechaLegible } from '@/i18n/fechas'
import { rutas } from '@/i18n/rutas'
import { resolverPlantilla } from '@/plantillas/plantillas'
import { Ic, Icono } from '@/components/iconos'
import { Accordion } from '@/components/Accordion'
import { EscalacionBloque } from '../../../_componentes/EscalacionBloque'
import { ValoracionArticulo } from '../../../_componentes/ValoracionArticulo'
import { PieDocumentacion } from '../../../_componentes/plantillas/documentacion/PieDocumentacion'

/**
 * Artículo del Centro de Ayuda. Server Component: título, cuerpo, pasos y FAQ
 * llegan en el HTML inicial. Un slug inexistente devuelve 404 (`not-found`).
 * Solo son islas de cliente el acordeón de la FAQ y la valoración.
 *
 * El cuerpo es el mismo con las dos plantillas (misma dirección, mismo título, párrafos,
 * pasos y FAQ, y el mismo ARIA): con `documentacion` solo cambia el cromo de la columna
 * —que aporta el armazón del layout— y se añade el pie con la última actualización.
 */
export default async function PaginaArticulo({
  params,
}: {
  params: Promise<{ idioma: string; slug: string }>
}) {
  const { idioma, slug } = await params
  if (!esIdioma(idioma)) redirect('/es')

  const t = traducir(idioma)
  const contenido = await cargarContenidoServidor(idioma)
  const articulo = articuloPorSlug(contenido, slug)
  if (!articulo) notFound()

  const categoria = contenido.categorias.find(c => c.id === articulo.categoria)
  const relacionados = articulo.relacionados
    .map(id => articuloPorId(contenido, id))
    .filter((a): a is NonNullable<typeof a> => a !== undefined)

  const fechaActualizado = fechaLegible(articulo.actualizado, idioma, FECHA_LARGA)
  const esDocumentacion = resolverPlantilla(contenido.plantilla) === 'documentacion'

  return (
    <main id="main-content" tabIndex={-1} className="focus:outline-none">
      {/* Con `documentacion` la barra lateral ya sitúa el artículo (con `aria-current`), así
          que las migas se sustituyen por el antetítulo de categoría de la referencia. */}
      {!esDocumentacion && (
        <div className="border-b border-slate-100 bg-white">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3">
            <nav aria-label={t('articulo.rutaNavegacion')}>
              <ol className="flex items-center gap-1.5 text-sm text-slate-600 list-none p-0 m-0 flex-wrap">
                <li>
                  <Link
                    href={rutas.inicio(idioma)}
                    className="text-[var(--acento)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded"
                  >
                    {t('articulo.raiz')}
                  </Link>
                </li>
                <li aria-hidden="true" className="text-slate-400">›</li>
                {categoria && (
                  <>
                    <li>
                      <Link
                        href={`${rutas.inicio(idioma)}?categoria=${categoria.slug}`}
                        className="text-[var(--acento)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded"
                      >
                        {categoria.nombre}
                      </Link>
                    </li>
                    <li aria-hidden="true" className="text-slate-400">›</li>
                  </>
                )}
                <li aria-current="page" className="text-slate-700 font-medium truncate max-w-[200px]">
                  {articulo.titulo}
                </li>
              </ol>
            </nav>
          </div>
        </div>
      )}

      <div
        className={
          esDocumentacion
            ? 'max-w-4xl box-content mx-auto px-4 sm:px-6 lg:px-12 py-10 lg:py-12'
            : 'max-w-3xl mx-auto px-4 sm:px-6 py-10'
        }
      >
        <header className="mb-8">
          {esDocumentacion && categoria && (
            <p className="flex items-center gap-2 text-[var(--acento)] text-sm font-semibold mb-2">
              <Icono nombre={categoria.icono} size={15} className="shrink-0" />
              {categoria.nombre}
            </p>
          )}
          <h1
            className={
              esDocumentacion
                ? 'text-2xl sm:text-3xl font-bold text-slate-900 leading-tight mb-3 pb-2 border-b border-slate-200'
                : 'text-2xl sm:text-3xl font-bold text-slate-900 leading-tight mb-3'
            }
            style={esDocumentacion ? undefined : { fontFamily: 'var(--font-serif), serif' }}
          >
            {articulo.titulo}
          </h1>
          <div className="flex items-center gap-3 text-slate-600 text-sm flex-wrap">
            <div className="flex items-center gap-1.5">
              <Ic.Clock size={13} />
              <span>
                {t('articulo.actualizado')} <time dateTime={articulo.actualizado}>{fechaActualizado}</time>
              </span>
            </div>
            <span aria-hidden="true">·</span>
            <span>{t('articulo.lectura', { minutos: articulo.minutosLectura })}</span>
          </div>
        </header>

        <article className="space-y-6 text-slate-700 text-[16px] leading-relaxed">
          {articulo.parrafos.map((parrafo, i) => (
            <p key={i}>{parrafo}</p>
          ))}

          <div className="rounded-2xl border border-[var(--acento-claro)] bg-[var(--acento-claro)] p-5 sm:p-6">
            <div className="flex items-center gap-2 mb-5">
              <div className="w-7 h-7 rounded-lg bg-[var(--acento)] flex items-center justify-center shrink-0">
                <Ic.FileText size={14} className="text-white" />
              </div>
              <h2 className="font-bold text-slate-900 text-base">{articulo.howTo.titulo}</h2>
            </div>
            <ol className="space-y-4 list-none p-0 m-0" aria-label={t('articulo.pasosAria', { titulo: articulo.howTo.titulo })}>
              {articulo.howTo.pasos.map((paso, i) => (
                <li key={i} className="flex items-start gap-4">
                  <span
                    aria-hidden="true"
                    className="shrink-0 w-8 h-8 rounded-full bg-[var(--acento)] text-white text-sm font-bold flex items-center justify-center mt-0.5"
                  >
                    {i + 1}
                  </span>
                  <div>
                    <p className="font-semibold text-slate-900 text-[15px] leading-snug">{paso.titulo}</p>
                    <p className="text-slate-600 text-sm mt-1 leading-relaxed">{paso.descripcion}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          {articulo.nota && (
            <div role="note" className="flex items-start gap-3 p-4 rounded-xl border border-sky-200 bg-sky-50">
              <Ic.Info size={17} className="shrink-0 text-sky-800 mt-0.5" />
              <p className="text-sm text-sky-900">
                <strong>{t('articulo.informacion')}</strong> {articulo.nota}
              </p>
            </div>
          )}

          <div>
            <h2 className="font-bold text-slate-900 text-lg mb-4 flex items-center gap-2">
              <Ic.HelpCircle size={18} className="text-[var(--acento)]" />
              {t('articulo.faq')}
            </h2>
            <div className="space-y-3">
              {articulo.faq.map((item, i) => (
                <Accordion key={i} pregunta={item.pregunta} respuesta={item.respuesta} />
              ))}
            </div>
          </div>
        </article>

        <ValoracionArticulo idioma={idioma} />

        {relacionados.length > 0 && (
          <div className="mt-8 pt-8 border-t border-slate-100">
            <h2 className="font-semibold text-slate-900 text-base mb-4">{t('articulo.relacionados')}</h2>
            <ul className="space-y-2 list-none p-0 m-0">
              {relacionados.map(rel => (
                <li key={rel.id}>
                  <Link
                    href={rutas.articulo(idioma, rel.slug)}
                    className="inline-flex items-center gap-2.5 text-sm text-[var(--acento)] hover:text-[var(--acento-hover)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded min-h-[44px]"
                  >
                    <Ic.ChevronRight size={14} className="text-[var(--acento)] shrink-0" />
                    {rel.titulo}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-10">
          <EscalacionBloque idioma={idioma} />
        </div>

        {esDocumentacion && <PieDocumentacion idioma={idioma} actualizado={articulo.actualizado} />}
      </div>
    </main>
  )
}
