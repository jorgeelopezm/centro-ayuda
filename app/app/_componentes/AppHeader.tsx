'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { LogoMarca } from './LogoMarca'
import { SelectorIdioma } from './SelectorIdioma'

export function AppHeader({
  idioma,
  empresa,
  logo,
  logoVersion,
}: {
  idioma: Idioma
  empresa?: string
  logo?: boolean
  logoVersion?: string | null
}) {
  const t = traducir(idioma)
  const pathname = usePathname()

  const inicioActivo = pathname === rutas.inicio(idioma)
  const panelActivo = pathname.startsWith(rutas.panel(idioma))

  const clasesEnlace = (activo: boolean) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 inline-flex items-center min-h-[44px] ${
      activo ? 'bg-[var(--acento-claro)] text-[var(--acento)]' : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
    }`

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200 supports-[backdrop-filter]:bg-white/80">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 min-h-24 py-3 flex items-center justify-between gap-4 flex-wrap">
        <Link
          href={rutas.inicio(idioma)}
          className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-2 rounded-lg"
          aria-label={t('general.irAlInicio')}
        >
          <LogoMarca idioma={idioma} empresa={empresa} logo={logo} logoVersion={logoVersion} />
        </Link>

        <div className="flex items-center gap-2 flex-wrap">
          <nav aria-label={t('nav.etiqueta')}>
            <ul className="flex items-center gap-0.5 list-none p-0 m-0">
              <li>
                <Link href={rutas.inicio(idioma)} aria-current={inicioActivo ? 'page' : undefined} className={clasesEnlace(inicioActivo)}>
                  {t('nav.inicio')}
                </Link>
              </li>
              {/* El sitio público no enlaza el panel: se entra por `rutas.panelInterno`.
                  Dentro del panel sí se muestra, para volver a él desde sus subpáginas. */}
              {panelActivo && (
                <li>
                  <Link href={rutas.panel(idioma)} aria-current="page" className={clasesEnlace(true)}>
                    {t('nav.panel')}
                  </Link>
                </li>
              )}
            </ul>
          </nav>

          <SelectorIdioma idioma={idioma} />
        </div>
      </div>
    </header>
  )
}
