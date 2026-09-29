'use client'

import { useState } from 'react'
import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { Ic } from '@/components/iconos'

/** «¿Te resultó útil?» del artículo. Isla de cliente con estado local. */
export function ValoracionArticulo({ idioma }: { idioma: Idioma }) {
  const t = traducir(idioma)
  const [valoracion, setValoracion] = useState<'si' | 'no' | null>(null)

  return (
    <div className="mt-10 pt-8 border-t border-slate-100">
      <h2 className="font-semibold text-slate-900 text-base mb-4">{t('articulo.util')}</h2>
      {valoracion === null ? (
        <div className="flex items-center gap-3 flex-wrap">
          <button
            type="button"
            onClick={() => setValoracion('si')}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:border-emerald-600 hover:text-emerald-800 hover:bg-emerald-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px]"
          >
            <Ic.ThumbsUp size={16} />
            {t('articulo.utilSi')}
          </button>
          <button
            type="button"
            onClick={() => setValoracion('no')}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:border-red-600 hover:text-red-800 hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px]"
          >
            <Ic.ThumbsDown size={16} />
            {t('articulo.utilNo')}
          </button>
        </div>
      ) : valoracion === 'si' ? (
        <div role="status" className="inline-flex items-center gap-2 text-emerald-800 bg-emerald-50 border border-emerald-200 px-4 py-2.5 rounded-lg text-sm font-medium">
          <Ic.CheckCircle size={16} className="text-emerald-700" />
          <span>{t('articulo.graciasSi')}</span>
        </div>
      ) : (
        <div role="status" className="inline-flex items-center gap-2 text-amber-900 bg-amber-50 border border-amber-200 px-4 py-2.5 rounded-lg text-sm font-medium">
          <Ic.Info size={16} className="text-amber-700" />
          <span>{t('articulo.graciasNo')}</span>
        </div>
      )}
    </div>
  )
}
