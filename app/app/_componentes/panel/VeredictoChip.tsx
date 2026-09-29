import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Ic } from '@/components/iconos'
import type { VeredictoChat } from '@/data/adminChats'

/**
 * Chip que representa el último veredicto de un chat con icono **y** texto: el
 * color solo acompaña, no es el único canal (WCAG 1.4.1). Mismo criterio que
 * `KcsChip` para los estados KCS.
 */
export function VeredictoChip({ veredicto }: { veredicto: VeredictoChat }) {
  const { t } = useTranslation()

  const mapa: Record<VeredictoChat, { icono: ReactNode; clases: string }> = {
    respondida: {
      icono: <Ic.CheckCircle size={11} className="text-emerald-700" />,
      clases: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    },
    sin_resultados: {
      icono: <Ic.HelpCircle size={11} className="text-amber-700" />,
      clases: 'bg-amber-50 text-amber-800 border-amber-200',
    },
    fuera_de_scope: {
      icono: <Ic.Info size={11} className="text-slate-700" />,
      clases: 'bg-slate-100 text-slate-800 border-slate-300',
    },
    escalar: {
      icono: <Ic.Warning size={11} className="text-rose-700" />,
      clases: 'bg-rose-50 text-rose-800 border-rose-200',
    },
  }

  const { icono, clases } = mapa[veredicto]
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${clases}`}>
      {icono}
      {t(`panelChats.veredictos.${veredicto}`)}
    </span>
  )
}
