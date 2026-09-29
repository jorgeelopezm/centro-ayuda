'use client'

import { usePathname } from 'next/navigation'
import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { Ic } from '@/components/iconos'

/**
 * Estado de error accesible cuando falla la fuente de contenido (task 3.5).
 * Sustituye la página en blanco por un `role="alert"` con texto e icono y un
 * botón para reintentar. El idioma se deduce del primer segmento.
 */
export default function ErrorContenido({ reset }: { error: Error; reset: () => void }) {
  const pathname = usePathname()
  const idioma: Idioma = pathname.startsWith('/pt') ? 'pt' : 'es'
  const t = traducir(idioma)

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="min-h-screen flex items-center justify-center bg-slate-50 px-4 focus:outline-none"
    >
      <div role="alert" className="max-w-md w-full rounded-2xl border border-red-200 bg-white p-6 text-center">
        <div className="mx-auto w-12 h-12 rounded-xl bg-red-50 flex items-center justify-center mb-4">
          <Ic.AlertCircle size={24} className="text-red-700" />
        </div>
        <h1 className="text-lg font-bold text-slate-900 mb-1">{t('estado.errorTitulo')}</h1>
        <p className="text-sm text-slate-600 mb-5">{t('estado.errorAyuda')}</p>
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
          style={{ background: 'var(--acento)' }}
        >
          <Ic.RefreshCw size={16} />
          {t('estado.reintentar')}
        </button>
      </div>
    </main>
  )
}
