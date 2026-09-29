import Link from 'next/link'
import type { ContenidoIdioma, Idioma } from '@/types'
import { articulosDestacados, contarPorCategoria } from '@/data'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { Ic, Icono } from '@/components/iconos'

/**
 * Inicio con la plantilla de documentación: índice de la base de conocimiento por
 * categoría (con sus artículos) y accesos populares. Server Component: reutiliza
 * `articulosDestacados` y `contarPorCategoria` sobre el contenido ya cargado, así que
 * todo llega en el HTML inicial. La búsqueda vive en la cabecera del armazón
 * (`CabeceraDocumentacion`), que usa `buscarArticulos`.
 */
export function InicioDocumentacion({
  idioma,
  contenido,
}: {
  idioma: Idioma
  contenido: ContenidoIdioma
}) {
  const t = traducir(idioma)
  const conteos = contarPorCategoria(contenido.articulos)
  const destacados = articulosDestacados(contenido)
  const grupos = contenido.categorias.map(categoria => ({
    categoria,
    articulos: contenido.articulos.filter(a => a.categoria === categoria.id),
  }))

  return (
    <>
      <div className="px-4 sm:px-6 lg:px-12 pt-10 lg:pt-12 pb-2">
        <div className="max-w-4xl mx-auto">
          <p className="flex items-center gap-2 text-[var(--acento)] text-sm font-semibold mb-2">
            <Ic.Terminal size={15} className="shrink-0" />
            {t('plantillaDocumentacion.navegacion.inicio')}
          </p>
          <h1 className="text-3xl font-bold text-slate-900 leading-tight mb-6 pb-2 border-b border-slate-200">
            {t('plantillaDocumentacion.inicio.titulo', { empresa: contenido.empresa })}
          </h1>
          <p className="text-lg text-slate-600 leading-relaxed">{t('plantillaDocumentacion.inicio.subtitulo')}</p>
        </div>
      </div>

      <div className="px-4 sm:px-6 lg:px-12 py-8">
        <div className="max-w-4xl mx-auto space-y-10">
          <section aria-labelledby="doc-indice-h2">
            <h2 id="doc-indice-h2" className="text-xl font-semibold text-slate-900 mb-5">
              {t('plantillaDocumentacion.inicio.indice')}
            </h2>

            {grupos.length === 0 && (
              <p className="text-sm text-slate-500">{t('plantillaDocumentacion.navegacion.vacio')}</p>
            )}

            <div className="space-y-6">
              {grupos.map(({ categoria, articulos }) => (
                <div key={categoria.id}>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-900 mb-2">
                    <Icono nombre={categoria.icono} size={16} className="shrink-0 text-[var(--acento)]" />
                    {categoria.nombre}
                    <span className="font-normal text-slate-500">
                      {t('general.articulos', { count: conteos[categoria.id] ?? 0 })}
                    </span>
                  </h3>
                  <ul className="space-y-0.5 list-none p-0 m-0 border-l border-slate-200 ml-2">
                    {articulos.map(articulo => (
                      <li key={articulo.id}>
                        <Link
                          href={rutas.articulo(idioma, articulo.slug)}
                          className="block pl-4 pr-2 py-2 text-sm text-slate-700 rounded-r-md border-l-2 border-transparent -ml-px hover:text-[var(--acento)] hover:bg-[var(--acento-claro)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                        >
                          {articulo.titulo}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>

          {destacados.length > 0 && (
            <section aria-labelledby="doc-populares-h2">
              <h2 id="doc-populares-h2" className="text-xl font-semibold text-slate-900 mb-3">
                {t('plantillaDocumentacion.inicio.populares')}
              </h2>
              <ul className="space-y-0.5 list-none p-0 m-0">
                {destacados.map(articulo => (
                  <li key={articulo.id}>
                    <Link
                      href={rutas.articulo(idioma, articulo.slug)}
                      className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:text-[var(--acento)] hover:bg-[var(--acento-claro)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                    >
                      <Ic.ChevronRight size={15} className="shrink-0 text-[var(--acento)]" />
                      {articulo.titulo}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  )
}
