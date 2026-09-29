import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'

/** Enlace para saltar al contenido principal. Server Component (solo texto). */
export function SkipLink({ idioma }: { idioma: Idioma }) {
  const t = traducir(idioma)
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[9999] focus:bg-[var(--acento)] focus:text-white focus:px-4 focus:py-2.5 focus:rounded-lg focus:text-sm focus:font-semibold focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-[var(--acento)]"
    >
      {t('general.saltarContenido')}
    </a>
  )
}
