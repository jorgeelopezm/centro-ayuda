'use client'

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRouter } from 'next/navigation'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'
import { Modal } from '@/components/Modal'
import { ArticuloForm } from '@/components/ArticuloForm'
import { derivarId } from '@/data/slug'
import type { ArticuloAdmin } from '@/data/admin'
import type { Categoria, Idioma } from '@/types'
import {
  descartarSugerencia,
  generarSugerencia,
  listarCandidatos,
  listarSugerencias,
  obtenerSugerencia,
  type Candidato,
  type FuenteSugerencia,
  type SugerenciaDetalle,
  type SugerenciaItem,
} from '@/data/sugerencias'

const FUENTES_FILTRO: readonly FuenteSugerencia[] = ['chat_escalado', 'pregunta_sin_resolver', 'documentacion_rag']

/**
 * Pestaña «Sugerencias» del Panel interno (spec `sugerencia-articulos-ia`).
 *
 * Trae del BFF los candidatos agregados de las tres fuentes
 * (`/api/admin/sugerencias/candidatos`) y la cola de borradores `pendiente`
 * (`/api/admin/sugerencias`). "Generar borrador con IA" dispara el pipeline
 * (bloqueante: la petición tarda lo que tarde el proveedor) y anuncia el
 * progreso por `aria-live`. Abrir una sugerencia precarga el `ArticuloForm`
 * existente en los dos idiomas; "Aceptar" reutiliza el alta de artículo
 * (`desdeSugerencia`) y "Descartar" archiva sin publicar nada. Mismo patrón de
 * accesibilidad que `PanelChats` (chips `aria-pressed`, `th scope="col"`,
 * objetivos táctiles ≥ 44×44 px).
 */
export function PanelSugerencias({ idioma, categorias }: { idioma: Idioma; categorias: Categoria[] }) {
  const { t } = useTranslation()
  const router = useRouter()

  const [fuente, setFuente] = useState<FuenteSugerencia | null>(null)
  const [candidatos, setCandidatos] = useState<Candidato[]>([])
  const [cargandoCandidatos, setCargandoCandidatos] = useState(true)
  const [errorCandidatos, setErrorCandidatos] = useState<string | null>(null)

  const [cola, setCola] = useState<SugerenciaItem[]>([])
  const [cargandoCola, setCargandoCola] = useState(true)
  const [errorCola, setErrorCola] = useState<string | null>(null)

  const [generando, setGenerando] = useState<string | null>(null) // `${fuente}:${referencia}`
  const [abriendo, setAbriendo] = useState<string | null>(null) // sugerenciaId
  const [avisoEstado, setAvisoEstado] = useState<string | null>(null)
  const [avisoError, setAvisoError] = useState<string | null>(null)
  const [formulario, setFormulario] = useState<{ sugerenciaId: string; inicial: ArticuloAdmin } | null>(null)

  const alSesionExpirada = useCallback(() => {
    router.replace(rutas.login(idioma))
  }, [idioma, router])

  const cargarCandidatos = useCallback(async () => {
    setCargandoCandidatos(true)
    setErrorCandidatos(null)
    const resp = await listarCandidatos(fuente ?? undefined).catch(() => null)
    if (resp === null) {
      setErrorCandidatos(t('panelSugerencias.errorCargarCandidatos'))
    } else if (resp.ok) {
      const cuerpo = (await resp.json()) as { items: Candidato[] }
      setCandidatos(cuerpo.items)
    } else if (resp.status === 401) {
      alSesionExpirada()
      return
    } else {
      setErrorCandidatos(t('panelSugerencias.errorCargarCandidatos'))
    }
    setCargandoCandidatos(false)
  }, [fuente, alSesionExpirada, t])

  const cargarCola = useCallback(async () => {
    setCargandoCola(true)
    setErrorCola(null)
    const resp = await listarSugerencias().catch(() => null)
    if (resp === null) {
      setErrorCola(t('panelSugerencias.errorCargarCola'))
    } else if (resp.ok) {
      const cuerpo = (await resp.json()) as { items: SugerenciaItem[] }
      setCola(cuerpo.items)
    } else if (resp.status === 401) {
      alSesionExpirada()
      return
    } else {
      setErrorCola(t('panelSugerencias.errorCargarCola'))
    }
    setCargandoCola(false)
  }, [alSesionExpirada, t])

  useEffect(() => {
    void cargarCandidatos()
  }, [cargarCandidatos])

  useEffect(() => {
    void cargarCola()
  }, [cargarCola])

  async function generar(candidato: Candidato) {
    const clave = `${candidato.fuente}:${candidato.referencia}`
    if (generando !== null) return
    setGenerando(clave)
    setAvisoError(null)
    setAvisoEstado(t('panelSugerencias.generando', { titulo: candidato.titulo_sugerido }))
    try {
      const resp = await generarSugerencia(candidato.fuente, candidato.referencia)
      if (resp.ok) {
        setAvisoEstado(t('panelSugerencias.generado', { titulo: candidato.titulo_sugerido }))
        await Promise.all([cargarCandidatos(), cargarCola()])
      } else if (resp.status === 401) {
        alSesionExpirada()
      } else if (resp.status === 404) {
        setAvisoEstado(null)
        setAvisoError(t('panelSugerencias.errorCandidatoObsoleto'))
        await cargarCandidatos()
      } else {
        setAvisoEstado(null)
        setAvisoError(t('panelSugerencias.errorGenerar'))
      }
    } catch {
      setAvisoEstado(null)
      setAvisoError(t('panelSugerencias.errorRed'))
    } finally {
      setGenerando(null)
    }
  }

  async function abrir(item: SugerenciaItem) {
    if (abriendo !== null) return
    setAbriendo(item.id)
    setAvisoError(null)
    try {
      const resp = await obtenerSugerencia(item.id)
      if (resp.ok) {
        const detalle = (await resp.json()) as SugerenciaDetalle
        const inicial: ArticuloAdmin = {
          // Mismo id de emergencia que el backend (`normalizar_slug` -> "" si el
          // título no tiene alfanuméricos): `app/sugerencias.py::generar_borrador`.
          id: derivarId(detalle.es.titulo) || 'borrador-sugerido',
          categoria: categorias[0]?.id ?? '',
          actualizado: new Date().toISOString().slice(0, 10),
          minutosLectura: 0,
          destacado: false,
          relacionados: [],
          es: detalle.es,
          pt: detalle.pt,
        }
        setFormulario({ sugerenciaId: item.id, inicial })
      } else if (resp.status === 401) {
        alSesionExpirada()
      } else {
        setAvisoError(t('panelSugerencias.errorAbrir'))
      }
    } catch {
      setAvisoError(t('panelSugerencias.errorRed'))
    } finally {
      setAbriendo(null)
    }
  }

  async function descartar(item: SugerenciaItem) {
    if (!window.confirm(t('panelSugerencias.confirmarDescartar', { titulo: item.titulo }))) return
    const resp = await descartarSugerencia(item.id)
    if (resp.ok) {
      setAvisoEstado(t('panelSugerencias.descartada'))
      await cargarCola()
    } else if (resp.status === 401) {
      alSesionExpirada()
    } else {
      setAvisoError(t('panelSugerencias.errorDescartar'))
    }
  }

  function alGuardadoFormulario() {
    setFormulario(null)
    setAvisoEstado(t('panelSugerencias.aceptada'))
    void cargarCola()
    void cargarCandidatos()
    router.refresh() // el contenido público refleja el artículo recién creado
  }

  const columnasCandidatos = ['fuente', 'titulo', 'idioma', 'prioridad', 'accion'] as const
  const columnasCola = ['titulo', 'fuente', 'creado', 'acciones'] as const

  return (
    <section aria-labelledby="sugerencias-h2" className="space-y-6">
      <div>
        <h2 id="sugerencias-h2" className="sr-only">
          {t('panelSugerencias.titulo')}
        </h2>
        <p className="text-slate-600 text-sm">{t('panelSugerencias.subtitulo')}</p>
      </div>

      <div role="status" aria-live="polite" className="min-h-[1.25rem]">
        {avisoEstado && (
          <p className="inline-flex items-center gap-2 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-2 rounded-lg">
            <Ic.CheckCircle size={15} className="text-emerald-700 shrink-0" />
            {avisoEstado}
          </p>
        )}
      </div>
      <div role="alert" aria-live="assertive" className="min-h-[1.25rem]">
        {avisoError && (
          <p className="inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
            <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
            {avisoError}
          </p>
        )}
      </div>

      {/* Candidatos ------------------------------------------------------- */}
      <section aria-labelledby="sugerencias-candidatos-h">
        <h3 id="sugerencias-candidatos-h" className="text-sm font-semibold text-slate-900 mb-3">
          {t('panelSugerencias.candidatosTitulo')}
        </h3>

        <div className="flex items-center gap-3 flex-wrap mb-3">
          <span id="sugerencias-filtro-fuente" className="text-sm font-medium text-slate-700">
            {t('panelSugerencias.filtroFuente')}
          </span>
          <div className="flex items-center gap-2 flex-wrap" role="group" aria-labelledby="sugerencias-filtro-fuente">
            <button
              type="button"
              onClick={() => setFuente(null)}
              aria-pressed={fuente === null}
              className={`px-3 rounded-full text-xs font-semibold border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                fuente === null
                  ? 'bg-[var(--acento)] text-white border-[var(--acento)]'
                  : 'bg-white text-slate-700 border-slate-500 hover:border-[var(--acento)] hover:text-[var(--acento)]'
              }`}
            >
              {t('panelSugerencias.filtroTodas')}
            </button>
            {FUENTES_FILTRO.map(f => {
              const activo = fuente === f
              return (
                <button
                  key={f}
                  type="button"
                  onClick={() => setFuente(f)}
                  aria-pressed={activo}
                  className={`px-3 rounded-full text-xs font-semibold border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                    activo
                      ? 'bg-[var(--acento)] text-white border-[var(--acento)]'
                      : 'bg-white text-slate-700 border-slate-500 hover:border-[var(--acento)] hover:text-[var(--acento)]'
                  }`}
                >
                  {t(`panelSugerencias.fuentes.${f}`)}
                </button>
              )
            })}
          </div>
        </div>

        {errorCandidatos && (
          <p role="alert" className="mb-3 inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
            <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
            {errorCandidatos}
          </p>
        )}

        <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
          {cargandoCandidatos ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t('panelSugerencias.cargando')}</p>
          ) : candidatos.length === 0 ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t('panelSugerencias.vacioCandidatos')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label={t('panelSugerencias.tablaCandidatosAria')}>
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {columnasCandidatos.map(col => (
                      <th
                        key={col}
                        scope="col"
                        className={`px-4 py-3 text-xs font-bold text-slate-600 uppercase tracking-wider whitespace-nowrap ${
                          col === 'prioridad' ? 'text-right' : 'text-left'
                        }`}
                      >
                        {t(`panelSugerencias.columnasCandidatos.${col}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {candidatos.map(c => {
                    const clave = `${c.fuente}:${c.referencia}`
                    const generandoEste = generando === clave
                    return (
                      <tr key={clave} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3.5">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border bg-slate-100 text-slate-800 border-slate-300">
                            {t(`panelSugerencias.fuentes.${c.fuente}`)}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-slate-800 font-medium max-w-[320px]">
                          <span className="leading-snug">{c.titulo_sugerido}</span>
                        </td>
                        <td className="px-4 py-3.5 text-slate-700 uppercase text-xs">{c.idioma}</td>
                        <td className="px-4 py-3.5 text-right tabular-nums text-slate-900 font-semibold">{c.prioridad}</td>
                        <td className="px-4 py-3.5">
                          {c.ya_generada ? (
                            <span className="text-xs text-slate-600 italic">{t('panelSugerencias.yaGenerada')}</span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => generar(c)}
                              aria-disabled={generando !== null}
                              aria-busy={generandoEste}
                              className={`inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-[var(--acento-claro)] text-[var(--acento)] bg-[var(--acento-claro)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px] whitespace-nowrap ${
                                generando !== null && !generandoEste ? 'opacity-60 cursor-not-allowed' : 'hover:border-[var(--acento)]'
                              }`}
                            >
                              {generandoEste ? (
                                <Ic.Loader size={13} className="animate-spin motion-reduce:animate-none" />
                              ) : (
                                <Ic.Sparkles size={13} />
                              )}
                              {generandoEste ? t('panelSugerencias.generandoBoton') : t('panelSugerencias.generarBoton')}
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {/* Cola de pendientes ------------------------------------------------ */}
      <section aria-labelledby="sugerencias-cola-h">
        <h3 id="sugerencias-cola-h" className="text-sm font-semibold text-slate-900 mb-3">
          {t('panelSugerencias.colaTitulo')}
        </h3>

        {errorCola && (
          <p role="alert" className="mb-3 inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
            <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
            {errorCola}
          </p>
        )}

        <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
          {cargandoCola ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t('panelSugerencias.cargando')}</p>
          ) : cola.length === 0 ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t('panelSugerencias.vacioCola')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label={t('panelSugerencias.tablaColaAria')}>
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {columnasCola.map(col => (
                      <th
                        key={col}
                        scope="col"
                        className="px-4 py-3 text-xs font-bold text-slate-600 uppercase tracking-wider whitespace-nowrap text-left"
                      >
                        {t(`panelSugerencias.columnasCola.${col}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {cola.map(item => {
                    const fecha = new Date(item.creado_en).toLocaleDateString(idioma, {
                      day: 'numeric', month: 'short', year: 'numeric',
                    })
                    return (
                      <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3.5 text-slate-800 font-medium max-w-[320px]">
                          <span className="leading-snug">{item.titulo}</span>
                        </td>
                        <td className="px-4 py-3.5">
                          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border bg-slate-100 text-slate-800 border-slate-300">
                            {t(`panelSugerencias.fuentes.${item.fuente}`)}
                          </span>
                        </td>
                        <td className="px-4 py-3.5 text-slate-600 whitespace-nowrap text-xs">
                          <time dateTime={item.creado_en}>{fecha}</time>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <button
                              type="button"
                              onClick={() => abrir(item)}
                              aria-busy={abriendo === item.id}
                              aria-label={t('panelSugerencias.abrirAria', { titulo: item.titulo })}
                              className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-[var(--acento-claro)] text-[var(--acento)] bg-[var(--acento-claro)] hover:border-[var(--acento)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px] whitespace-nowrap"
                            >
                              {abriendo === item.id ? (
                                <Ic.Loader size={13} className="animate-spin motion-reduce:animate-none" />
                              ) : (
                                <Ic.Eye size={13} />
                              )}
                              {t('panelSugerencias.abrir')}
                            </button>
                            <button
                              type="button"
                              onClick={() => descartar(item)}
                              aria-label={t('panelSugerencias.descartarAria', { titulo: item.titulo })}
                              className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-red-200 text-red-800 bg-red-50 hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                            >
                              <Ic.Trash size={13} />
                              {t('panelSugerencias.descartar')}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {formulario && (
        <Modal labelledBy="form-articulo-h" onCerrar={() => setFormulario(null)} cerrarAlClicarFondo={false}>
          <ArticuloForm
            categorias={categorias}
            modo="crear"
            inicial={formulario.inicial}
            sugerenciaId={formulario.sugerenciaId}
            onCerrar={() => setFormulario(null)}
            onGuardado={alGuardadoFormulario}
          />
        </Modal>
      )}
    </section>
  )
}
