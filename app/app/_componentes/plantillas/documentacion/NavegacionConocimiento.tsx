'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { ContenidoIdioma, Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { Ic, Icono } from '@/components/iconos'

/**
 * Navegación lateral de la plantilla de documentación: la base de conocimiento agrupada
 * por categoría, con los artículos de cada una (mismo filtro que `contarPorCategoria`),
 * derivada del contenido que el layout ya cargó. No hay endpoint ni dato nuevos.
 *
 * Es Client Component por dos motivos concretos: marcar la página en curso con
 * `usePathname()` (mismo patrón que `AppHeader`) y el panel deslizante en pantalla
 * estrecha (el armazón guarda el estado y lo comparten cabecera y barra). Se prerenderiza,
 * así que categorías y títulos salen en el HTML inicial.
 *
 * Como en la referencia, cada categoría es un encabezado con sus artículos siempre a la
 * vista (sin plegado): el artículo en curso nunca queda oculto y no hay controles extra
 * que tabular. El título «Base de conocimiento» se conserva solo para lectores de
 * pantalla, como encabezado de los grupos.
 */
export function NavegacionConocimiento({
  idioma,
  contenido,
  abierta,
  onCerrar,
}: {
  idioma: Idioma
  contenido: ContenidoIdioma
  abierta: boolean
  onCerrar: () => void
}) {
  const t = traducir(idioma)
  const pathname = usePathname()
  const inicioActivo = pathname === rutas.inicio(idioma)

  const grupos = contenido.categorias.map(categoria => ({
    categoria,
    articulos: contenido.articulos.filter(a => a.categoria === categoria.id),
  }))

  return (
    <>
      {abierta && (
        <button
          type="button"
          aria-label={t('plantillaDocumentacion.menu.cerrar')}
          onClick={onCerrar}
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
        />
      )}

      <aside
        id="nav-conocimiento"
        aria-label={t('plantillaDocumentacion.navegacion.etiqueta')}
        className={`fixed inset-y-0 left-0 z-30 w-72 max-w-[85%] overflow-y-auto bg-slate-50 border-r border-slate-200 transition-transform duration-200 lg:static lg:z-auto lg:w-64 lg:max-w-none lg:shrink-0 lg:h-full lg:translate-x-0 ${
          abierta ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <nav className="py-6 px-4">
          <Link
            href={rutas.inicio(idioma)}
            aria-current={inicioActivo ? 'page' : undefined}
            onClick={onCerrar}
            className={`flex items-center gap-2 px-2 py-2 rounded-r-md border-l-2 text-sm mb-8 min-h-[44px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 ${
              inicioActivo
                ? 'border-[var(--acento)] bg-[var(--acento-claro)] text-[var(--acento)] font-medium'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100'
            }`}
          >
            <Ic.Terminal size={16} className="shrink-0 text-[var(--acento)]" />
            {t('plantillaDocumentacion.navegacion.inicio')}
          </Link>

          <h2 className="sr-only">{t('plantillaDocumentacion.navegacion.titulo')}</h2>

          {contenido.categorias.length === 0 && (
            <p className="px-2 text-sm text-slate-600">{t('plantillaDocumentacion.navegacion.vacio')}</p>
          )}

          {grupos.map(({ categoria, articulos }) => (
            <div key={categoria.id} className="mb-8">
              <h3 className="flex items-center gap-2 text-xs font-semibold text-slate-900 uppercase tracking-wider mb-3 px-2">
                <Icono nombre={categoria.icono} size={14} className="shrink-0 text-[var(--acento)]" />
                {categoria.nombre}
              </h3>
              <ul className="space-y-1 list-none p-0 m-0">
                {articulos.map(articulo => {
                  const actual = pathname === rutas.articulo(idioma, articulo.slug)
                  return (
                    <li key={articulo.id}>
                      <Link
                        href={rutas.articulo(idioma, articulo.slug)}
                        aria-current={actual ? 'page' : undefined}
                        onClick={onCerrar}
                        className={`flex items-center px-2 py-1.5 text-sm rounded-r-md border-l-2 min-h-[44px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 ${
                          actual
                            ? 'border-[var(--acento)] bg-[var(--acento-claro)] text-[var(--acento)] font-medium'
                            : 'border-transparent text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                        }`}
                      >
                        {articulo.titulo}
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </nav>
      </aside>
    </>
  )
}
