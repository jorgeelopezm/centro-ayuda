'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import type { ContenidoIdioma, Idioma } from '@/types'
import { buscarArticulos } from '@/data'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'
import { LogoMarca } from '../../LogoMarca'
import { SelectorIdioma } from '../../SelectorIdioma'

/**
 * Barra superior de la plantilla de documentación: marca (`LogoMarca`, la misma de la
 * plantilla predeterminada), buscador y el control de la barra lateral en pantalla
 * estrecha. Es Client Component porque el buscador filtra en cliente y el botón de menú
 * comparte estado con la barra lateral (el armazón es quien lo guarda).
 *
 * El buscador reutiliza `buscarArticulos` (la misma búsqueda del inicio de la plantilla
 * predeterminada), así que con las dos plantillas se obtienen los mismos resultados del
 * portal en el idioma activo. Los resultados se anuncian en una región `aria-live`.
 *
 * Como en la referencia, el buscador queda centrado entre marca y acciones y se enfoca con
 * Ctrl+K (⌘K en Mac). Deliberadamente no se usa «/»: un atajo de un solo carácter choca con
 * WCAG 2.1.4 si no se puede desactivar.
 *
 * A la derecha, como en la referencia: idioma, un separador, el modo noche y el enlace a
 * GitHub (solo si el portal lo configuró). El panel interno ya no se enlaza: se entra por
 * `rutas.panelInterno` (`/es/panel-interno`).
 */
const BOTON_ICONO =
  'inline-flex items-center justify-center w-11 h-11 shrink-0 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1'

export function CabeceraDocumentacion({
  idioma,
  contenido,
  navAbierta,
  onAlternarNav,
  oscuro,
  onAlternarTema,
}: {
  idioma: Idioma
  contenido: ContenidoIdioma
  navAbierta: boolean
  onAlternarNav: () => void
  /** ¿Se ve el modo noche? (estado del botón, `aria-pressed`). */
  oscuro: boolean
  onAlternarTema: () => void
}) {
  const t = traducir(idioma)
  const [consulta, setConsulta] = useState('')
  // La API ya solo admite https://github.com/…; se revalida aquí (defensa en
  // profundidad) para no pintar nunca un enlace «GitHub» hacia otro sitio.
  const githubUrl = /^https:\/\/(www\.)?github\.com\//.test(contenido.githubUrl ?? '') ? contenido.githubUrl : null
  const campoRef = useRef<HTMLInputElement>(null)
  // El servidor no conoce la plataforma: se pinta «Ctrl» y se corrige tras montar,
  // para no provocar un desajuste de hidratación.
  const [esMac, setEsMac] = useState(false)

  useEffect(() => {
    setEsMac(/Mac|iPhone|iPad/.test(navigator.platform))
    const alPulsar = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        campoRef.current?.focus()
        campoRef.current?.select()
      }
    }
    document.addEventListener('keydown', alPulsar)
    return () => document.removeEventListener('keydown', alPulsar)
  }, [])

  const termino = consulta.trim()
  const resultados = useMemo(
    () => (termino === '' ? [] : buscarArticulos(contenido, termino).slice(0, 6)),
    [contenido, termino],
  )

  return (
    <header className="sticky top-0 z-30 shrink-0 bg-white/95 backdrop-blur border-b border-slate-200 supports-[backdrop-filter]:bg-white/80 lg:static">
      {/* En `lg` marca y acciones son columnas flexibles iguales, así que el buscador queda
          centrado (la referencia usa `w-1/4`, que desbordaría con un nombre de empresa largo). */}
      <div className="flex items-center gap-3 sm:gap-4 px-3 sm:px-6 lg:px-8 py-2 sm:py-0 sm:h-16 flex-wrap sm:flex-nowrap">
        <div className="flex items-center gap-2 shrink-0 lg:flex-1">
          <button
            type="button"
            onClick={onAlternarNav}
            aria-expanded={navAbierta}
            aria-controls="nav-conocimiento"
            aria-label={
              navAbierta
                ? t('plantillaDocumentacion.menu.cerrar')
                : t('plantillaDocumentacion.menu.abrir')
            }
            className="lg:hidden inline-flex items-center justify-center w-11 h-11 shrink-0 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1"
          >
            <Ic.Menu size={22} />
          </button>

          <Link
            href={rutas.inicio(idioma)}
            aria-label={t('general.irAlInicio')}
            className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-2"
          >
            <LogoMarca
              idioma={idioma}
              empresa={contenido.empresa}
              logo={contenido.logo}
              logoVersion={contenido.logoVersion}
              compacto
            />
          </Link>
        </div>

        {/* La envoltura es el destino del enlace «Buscar» del pie: recibe el foco con
            `tabIndex={-1}` (mismo patrón que el `SkipLink`), sin añadir parada de tabulación. */}
        <div
          id="buscar-documentacion"
          tabIndex={-1}
          className="order-last w-full sm:order-none sm:w-auto sm:flex-1 sm:max-w-md lg:flex-initial lg:w-full relative focus:outline-none"
        >
          <label htmlFor="buscar-documentacion-campo" className="sr-only">
            {t('plantillaDocumentacion.buscar.etiqueta')}
          </label>
          <div role="search" className="relative">
            <span className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
              <Ic.Search size={18} className="text-slate-400" />
            </span>
            <input
              ref={campoRef}
              id="buscar-documentacion-campo"
              type="search"
              value={consulta}
              onChange={e => setConsulta(e.target.value)}
              placeholder={t('plantillaDocumentacion.buscar.marcador')}
              aria-describedby="buscar-documentacion-resultados"
              aria-keyshortcuts="Control+K Meta+K"
              className="w-full pl-10 pr-3 md:pr-20 py-2.5 rounded-full border border-slate-400 bg-slate-50 text-slate-900 text-sm focus:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
            />
            {/* Indicador visual del atajo; el atajo en sí se anuncia con `aria-keyshortcuts`.
                Se oculta al escribir para no tapar el texto ni el botón de borrar del campo. */}
            {consulta === '' && (
              <span
                aria-hidden="true"
                className="hidden md:flex absolute inset-y-0 right-3 items-center gap-1 pointer-events-none"
              >
                <kbd className="border border-slate-300 rounded bg-white px-1.5 text-[11px] font-mono text-slate-600 shadow-sm">
                  {esMac ? '⌘' : 'Ctrl'}
                </kbd>
                <kbd className="border border-slate-300 rounded bg-white px-1.5 text-[11px] font-mono text-slate-600 shadow-sm">
                  K
                </kbd>
              </span>
            )}
          </div>

          <div
            id="buscar-documentacion-resultados"
            aria-live="polite"
            className="absolute left-0 right-0 top-full mt-2 z-40 empty:hidden"
          >
            {termino !== '' &&
              (resultados.length > 0 ? (
                <div className="rounded-xl border border-slate-200 bg-white shadow-lg p-3">
                  <p className="text-xs font-semibold text-slate-500 mb-2">
                    {t('plantillaDocumentacion.buscar.resultados', {
                      count: resultados.length,
                      termino,
                    })}
                  </p>
                  <ul className="space-y-0.5 list-none p-0 m-0">
                    {resultados.map(articulo => (
                      <li key={articulo.id}>
                        <Link
                          href={rutas.articulo(idioma, articulo.slug)}
                          className="flex items-start gap-2 px-2 py-2 rounded-lg text-sm text-slate-700 hover:text-[var(--acento)] hover:bg-[var(--acento-claro)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                        >
                          <Ic.ChevronRight size={14} className="shrink-0 mt-1 text-[var(--acento)]" />
                          <span>{articulo.titulo}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="rounded-xl border border-slate-200 bg-white shadow-lg px-3 py-2 text-sm text-slate-600">
                  {t('plantillaDocumentacion.buscar.sinResultados', { termino })}
                </p>
              ))}
          </div>
        </div>

        <div className="ml-auto sm:ml-0 flex items-center justify-end gap-1 shrink-0 lg:flex-1">
          <SelectorIdioma idioma={idioma} />
          <span aria-hidden="true" className="hidden md:block w-px h-5 bg-slate-200 mx-2" />
          {/* Conmutador con etiqueta fija y `aria-pressed`: el estado se anuncia sin
              cambiar el nombre del control. El icono muestra lo que se activará. */}
          <button
            type="button"
            onClick={onAlternarTema}
            aria-pressed={oscuro}
            aria-label={t('plantillaDocumentacion.tema.oscuro')}
            title={t('plantillaDocumentacion.tema.oscuro')}
            className={BOTON_ICONO}
          >
            {oscuro ? <Ic.Sun size={20} /> : <Ic.Moon size={20} />}
          </button>
          {githubUrl && (
            <a
              href={githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={t('plantillaDocumentacion.github')}
              title={t('plantillaDocumentacion.github')}
              className={BOTON_ICONO}
            >
              <Ic.Github size={20} />
            </a>
          )}
        </div>
      </div>
    </header>
  )
}
