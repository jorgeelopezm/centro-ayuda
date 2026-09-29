import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'

export type Pestana<Id extends string> = {
  id: Id
  etiqueta: string
  contenido: ReactNode
}

/**
 * Pestañas accesibles (patrón WAI-ARIA Tabs). La lista lleva `role="tablist"`
 * con nombre accesible; cada control es un `role="tab"` con roving tabindex
 * enlazado a su `role="tabpanel"`. El foco se mueve con las flechas (activación
 * automática) e Inicio/Fin. La pestaña activa se distingue con `aria-selected`
 * y un cambio de borde/fondo, no solo por color.
 *
 * Las pestañas llegan ya filtradas por quien las monta (p. ej. la pestaña de
 * Administrador solo se incluye si la sesión es Administrador); este componente no
 * decide visibilidad.
 */
export function Tabs<Id extends string>({
  pestanas,
  activa,
  onCambio,
  etiquetaLista,
}: {
  pestanas: Pestana<Id>[]
  activa: Id
  onCambio: (id: Id) => void
  etiquetaLista: string
}) {
  const baseId = useId()
  const refsBoton = useRef(new Map<Id, HTMLButtonElement>())

  const idTab = (id: Id) => `${baseId}-tab-${id}`
  const idPanel = (id: Id) => `${baseId}-panel-${id}`

  function moverFoco(indice: number) {
    const total = pestanas.length
    const destino = pestanas[((indice % total) + total) % total]
    onCambio(destino.id)
    refsBoton.current.get(destino.id)?.focus()
  }

  function alTeclado(evento: KeyboardEvent<HTMLButtonElement>, indice: number) {
    switch (evento.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        evento.preventDefault()
        moverFoco(indice + 1)
        break
      case 'ArrowLeft':
      case 'ArrowUp':
        evento.preventDefault()
        moverFoco(indice - 1)
        break
      case 'Home':
        evento.preventDefault()
        moverFoco(0)
        break
      case 'End':
        evento.preventDefault()
        moverFoco(pestanas.length - 1)
        break
    }
  }

  return (
    <div>
      <div role="tablist" aria-label={etiquetaLista} className="flex items-center gap-2 flex-wrap border-b border-slate-200">
        {pestanas.map((pestana, indice) => {
          const seleccionada = pestana.id === activa
          return (
            <button
              key={pestana.id}
              type="button"
              role="tab"
              id={idTab(pestana.id)}
              aria-selected={seleccionada}
              aria-controls={idPanel(pestana.id)}
              tabIndex={seleccionada ? 0 : -1}
              ref={nodo => {
                if (nodo) refsBoton.current.set(pestana.id, nodo)
                else refsBoton.current.delete(pestana.id)
              }}
              onClick={() => onCambio(pestana.id)}
              onKeyDown={evento => alTeclado(evento, indice)}
              className={`-mb-px inline-flex items-center px-4 rounded-t-lg text-sm font-semibold border border-b-0 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                seleccionada
                  ? 'bg-white text-[var(--acento)] border-slate-200 border-t-2 border-t-[color:var(--acento)]'
                  : 'bg-slate-50 text-slate-600 border-transparent hover:text-[var(--acento)] hover:bg-white'
              }`}
            >
              {pestana.etiqueta}
            </button>
          )
        })}
      </div>

      {pestanas.map(pestana => (
        <div
          key={pestana.id}
          role="tabpanel"
          id={idPanel(pestana.id)}
          aria-labelledby={idTab(pestana.id)}
          hidden={pestana.id !== activa}
          className="pt-8"
        >
          {pestana.contenido}
        </div>
      ))}
    </div>
  )
}
