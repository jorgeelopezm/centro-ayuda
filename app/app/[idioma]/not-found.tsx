'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'

/**
 * Pantalla "no encontrado" (task 2.4). La dispara `notFound()` de un artículo
 * inexistente o una dirección sin ruta. El idioma se deduce del primer segmento.
 */
export default function NoEncontrado() {
  const pathname = usePathname()
  const idioma: Idioma = pathname.startsWith('/pt') ? 'pt' : 'es'
  const t = traducir(idioma)

  return (
    <main id="main-content" tabIndex={-1} className="focus:outline-none">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-20 text-center">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-amber-50 mb-5">
          <Ic.AlertCircle size={26} className="text-amber-700" />
        </div>
        <h1 className="text-2xl font-bold text-slate-900 mb-2" style={{ fontFamily: 'var(--font-serif), serif' }}>
          {t('articulo.noEncontrado')}
        </h1>
        <p className="text-slate-600 text-[15px] max-w-md mx-auto">{t('articulo.noEncontradoAyuda')}</p>
        <Link
          href={rutas.inicio(idioma)}
          className="mt-6 inline-flex items-center gap-2 px-5 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
          style={{ background: 'var(--acento)' }}
        >
          {t('articulo.volverInicio')}
        </Link>
      </div>
    </main>
  )
}
