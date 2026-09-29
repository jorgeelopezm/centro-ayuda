'use client'

import { useId, useState } from 'react'
import { Ic } from './iconos'

/**
 * Acordeón de una pregunta frecuente. El botón vive dentro de un <h3> para no
 * romper la jerarquía de encabezados; `aria-expanded` y `aria-controls` lo
 * enlazan con el panel, que se identifica con `role="region"`.
 */
export function Accordion({ pregunta, respuesta }: { pregunta: string; respuesta: string }) {
  const [abierto, setAbierto] = useState(false)
  const id = useId()
  const idBoton = `${id}-btn`
  const idPanel = `${id}-panel`

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden">
      <h3>
        <button
          type="button"
          id={idBoton}
          onClick={() => setAbierto(o => !o)}
          aria-expanded={abierto}
          aria-controls={idPanel}
          className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left bg-white hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--acento-foco)] transition-colors min-h-[56px]"
        >
          <span className="font-medium text-slate-900 text-[15px] leading-snug">{pregunta}</span>
          <Ic.ChevronDown size={18} className={`shrink-0 text-slate-400 transition-transform ${abierto ? 'rotate-180' : ''}`} />
        </button>
      </h3>
      <div
        id={idPanel}
        role="region"
        aria-labelledby={idBoton}
        hidden={!abierto}
        className="px-5 pb-5 pt-2 bg-slate-50 text-slate-700 text-sm leading-relaxed"
      >
        {respuesta}
      </div>
    </div>
  )
}
