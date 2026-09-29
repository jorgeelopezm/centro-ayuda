'use client'

import { useEffect, useState, type ReactNode } from 'react'
import type { Idioma } from '@/types'
import i18n from '@/i18n/config'
import { traducir } from '@/i18n/traducir'
import { Ic } from '@/components/iconos'

/**
 * El panel reutiliza los componentes de la SPA (formularios, chips, tabla), que
 * usan `useTranslation` de react-i18next. Este contenedor fija el idioma del
 * segmento en la instancia de i18n **antes** de renderizarlos y espera a que
 * esté listo, de modo que el árbol de cliente no se pinta con el idioma por
 * defecto. El texto de carga usa el traductor isomórfico (no depende de i18n).
 */
export function PanelI18n({ idioma, children }: { idioma: Idioma; children: ReactNode }) {
  const [listo, setListo] = useState(false)

  useEffect(() => {
    let vivo = true
    void i18n.changeLanguage(idioma).then(() => {
      if (vivo) setListo(true)
    })
    return () => {
      vivo = false
    }
  }, [idioma])

  if (!listo) {
    const t = traducir(idioma)
    return (
      <div
        role="status"
        aria-live="polite"
        className="min-h-[60vh] flex flex-col items-center justify-center gap-3 text-slate-700"
      >
        <Ic.Loader size={28} className="animate-spin text-[var(--acento)] motion-reduce:animate-none" />
        <p className="text-sm font-medium">{t('estado.cargando')}</p>
      </div>
    )
  }

  return <>{children}</>
}
