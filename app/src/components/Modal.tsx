import { useEffect, useRef, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * Diálogo modal accesible (WCAG 2.2 AA), sin dependencias externas:
 * - `role="dialog"` + `aria-modal="true"` y nombre accesible por `aria-labelledby`.
 * - Foco inicial dentro del diálogo al abrir y retorno al disparador al cerrar.
 * - Cierre con Esc y, si `cerrarAlClicarFondo`, con clic en el fondo.
 * - Trampa de foco: Tab/Shift+Tab ciclan dentro; el fondo no recibe foco.
 * - Se renderiza por portal fuera de `#root` y marca `#root` como `inert` mientras
 *   está abierto, de modo que el fondo queda inerte también para lectores de
 *   pantalla y teclado (no solo cubierto por el overlay). El cuerpo no hace scroll.
 */

const FOCUSABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusablesDe(cont: HTMLElement | null): HTMLElement[] {
  if (!cont) return []
  return Array.from(cont.querySelectorAll<HTMLElement>(FOCUSABLES)).filter(
    el => el.offsetParent !== null || el === document.activeElement,
  )
}

export function Modal({
  labelledBy,
  onCerrar,
  children,
  cerrarAlClicarFondo = true,
}: {
  /** id del encabezado que da nombre al diálogo (aria-labelledby). */
  labelledBy: string
  onCerrar: () => void
  children: ReactNode
  /** Si es false, el clic en el fondo no cierra (evita perder trabajo sin querer). */
  cerrarAlClicarFondo?: boolean
}) {
  const dialogoRef = useRef<HTMLDivElement>(null)
  const disparadorRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    // Recuerda quién abrió el modal para devolverle el foco al cerrar.
    disparadorRef.current = document.activeElement as HTMLElement | null
    const focusables = focusablesDe(dialogoRef.current)
    ;(focusables[0] ?? dialogoRef.current)?.focus()

    const overflowPrevio = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // Deja el resto de la app inerte (sin foco, sin puntero, oculta para AT)
    // mientras el diálogo está abierto. El diálogo vive fuera de #root (portal),
    // así que no se ve afectado por su propio `inert`.
    const raiz = document.getElementById('root')
    raiz?.setAttribute('inert', '')
    raiz?.setAttribute('aria-hidden', 'true')

    return () => {
      document.body.style.overflow = overflowPrevio
      raiz?.removeAttribute('inert')
      raiz?.removeAttribute('aria-hidden')
      // Devuelve el foco al control que abrió el diálogo (ya no inerte).
      disparadorRef.current?.focus?.()
    }
  }, [])

  function alTeclado(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      onCerrar()
      return
    }
    if (e.key !== 'Tab') return
    const focusables = focusablesDe(dialogoRef.current)
    if (focusables.length === 0) {
      e.preventDefault()
      return
    }
    const primero = focusables[0]
    const ultimo = focusables[focusables.length - 1]
    const activo = document.activeElement
    if (e.shiftKey && (activo === primero || activo === dialogoRef.current)) {
      e.preventDefault()
      ultimo.focus()
    } else if (!e.shiftKey && activo === ultimo) {
      e.preventDefault()
      primero.focus()
    }
  }

  return createPortal(
    // Overlay: cubre el viewport y, si procede, captura el clic de fondo para cerrar.
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 sm:p-6"
      onMouseDown={e => {
        // Solo cierra si el clic empezó en el fondo, no dentro del diálogo.
        if (cerrarAlClicarFondo && e.target === e.currentTarget) onCerrar()
      }}
    >
      <div
        ref={dialogoRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        tabIndex={-1}
        onKeyDown={alTeclado}
        className="relative w-full max-w-3xl my-4 focus:outline-none"
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
