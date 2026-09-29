import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { EstadoKcs } from '@/types'
import { Ic } from './iconos'

/**
 * El estado se comunica siempre con icono **y** texto. El color acompaña,
 * nunca es el único canal (WCAG 1.4.1).
 */
export function KcsChip({ estado }: { estado: EstadoKcs }) {
  const { t } = useTranslation()

  const mapa: Record<EstadoKcs, { icono: ReactNode; clases: string }> = {
    nueva: {
      icono: <Ic.CircleDot size={8} className="text-blue-600" />,
      clases: 'bg-blue-50 text-blue-800 border-blue-200',
    },
    revision: {
      icono: <Ic.Clock size={11} className="text-amber-700" />,
      clases: 'bg-amber-50 text-amber-800 border-amber-200',
    },
    cubierta: {
      icono: <Ic.CheckCircle size={11} className="text-emerald-700" />,
      clases: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    },
  }

  const { icono, clases } = mapa[estado]

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${clases}`}>
      {icono}
      {t(`kcs.${estado}`)}
    </span>
  )
}
