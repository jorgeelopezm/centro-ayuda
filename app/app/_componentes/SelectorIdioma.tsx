'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useParams } from 'next/navigation'
import { IDIOMAS, type Idioma } from '@/types'
import { articuloPorId, articuloPorSlug, cargarContenido } from '@/data'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'

/**
 * Cambia de idioma conservando la pantalla actual. En un artículo, los
 * segmentos de dirección difieren entre idiomas, así que se traduce pasando por
 * el identificador estable del artículo. Ese contenido del otro idioma se
 * obtiene **bajo demanda** en el cliente (la página solo carga el idioma
 * activo). Hasta resolverlo, el destino cae en el inicio del idioma.
 */
export function SelectorIdioma({ idioma }: { idioma: Idioma }) {
  const t = traducir(idioma)
  const pathname = usePathname()
  const params = useParams()
  const slug = typeof params?.slug === 'string' ? params.slug : undefined
  const esArticulo = Boolean(slug) && pathname.includes(`/${idioma}/articulo/`)

  const [hrefsArticulo, setHrefsArticulo] = useState<Partial<Record<Idioma, string>>>({})

  useEffect(() => {
    if (!esArticulo || !slug) return
    let cancelado = false
    void (async () => {
      try {
        const actual = await cargarContenido(idioma)
        const articulo = articuloPorSlug(actual, slug)
        if (!articulo) return
        const otros = IDIOMAS.filter(c => c !== idioma)
        const contenidos = await Promise.all(otros.map(c => cargarContenido(c)))
        if (cancelado) return
        const mapa: Partial<Record<Idioma, string>> = {}
        otros.forEach((codigo, i) => {
          const eq = articuloPorId(contenidos[i], articulo.id)
          mapa[codigo] = eq ? rutas.articulo(codigo, eq.slug) : rutas.inicio(codigo)
        })
        setHrefsArticulo(mapa)
      } catch {
        // Se conserva el destino por defecto (inicio del idioma).
      }
    })()
    return () => {
      cancelado = true
    }
  }, [esArticulo, slug, idioma])

  function destino(codigo: Idioma): string {
    if (esArticulo) return hrefsArticulo[codigo] ?? rutas.inicio(codigo)
    if (pathname.includes(`/${idioma}/panel/usuarios`)) return rutas.usuarios(codigo)
    if (pathname.startsWith(rutas.panel(idioma))) return rutas.panel(codigo)
    if (pathname === rutas.login(idioma)) return rutas.login(codigo)
    return rutas.inicio(codigo)
  }

  return (
    <div className="flex items-center gap-1.5">
      <span id="etiqueta-idioma" className="flex items-center gap-1 text-xs font-medium text-slate-500">
        <Ic.Globe size={13} className="text-slate-400" />
        {t('idioma.etiqueta')}
      </span>
      <ul className="flex items-center gap-0.5 list-none p-0 m-0" aria-labelledby="etiqueta-idioma">
        {IDIOMAS.map(codigo => {
          const activo = codigo === idioma
          return (
            <li key={codigo}>
              <Link
                href={destino(codigo)}
                hrefLang={codigo}
                aria-current={activo ? 'true' : undefined}
                aria-label={
                  activo
                    ? t('idioma.actual', { idioma: t(`idioma.${codigo}`) })
                    : t('idioma.cambiarA', { idioma: t(`idioma.${codigo}`) })
                }
                className={`inline-flex items-center justify-center min-w-[44px] min-h-[44px] px-2 rounded-md text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 ${
                  activo
                    ? 'bg-[var(--acento-claro)] text-[var(--acento)] font-bold underline underline-offset-4 decoration-2'
                    : 'text-slate-600 font-medium hover:text-slate-900 hover:bg-slate-100'
                }`}
              >
                {codigo.toUpperCase()}
              </Link>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
