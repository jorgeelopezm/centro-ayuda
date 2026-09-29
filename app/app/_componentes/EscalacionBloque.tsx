import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { Ic } from '@/components/iconos'

/** Bloque de escalado a soporte. Server Component (solo texto + enlace mailto). */
export function EscalacionBloque({ idioma }: { idioma: Idioma }) {
  const t = traducir(idioma)
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div className="flex items-start gap-4">
        <div className="shrink-0 w-11 h-11 rounded-full bg-[var(--acento-claro)] flex items-center justify-center">
          <Ic.HelpCircle size={22} className="text-[var(--acento)]" />
        </div>
        <div>
          <p className="font-semibold text-slate-900 text-[15px]">{t('escalamiento.titulo')}</p>
          <p className="text-slate-500 text-sm mt-0.5">{t('escalamiento.horario')}</p>
        </div>
      </div>
      <a
        href="mailto:soporte@empresa.example"
        className="shrink-0 inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] transition-opacity min-h-[44px]"
        style={{ background: 'var(--acento)' }}
      >
        <Ic.Mail size={16} />
        {t('escalamiento.boton')}
      </a>
    </div>
  )
}
