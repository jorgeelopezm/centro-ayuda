'use client'

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useRouter } from 'next/navigation'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'
import type { Idioma } from '@/types'
import {
  listarChats,
  obtenerMetricasChats,
  type ChatItem,
  type ChatMetricas,
  type FiltrosChats,
  type VeredictoChat,
} from '@/data/adminChats'
import { DetalleChatModal } from './DetalleChatModal'
import { VeredictoChip } from './VeredictoChip'

const VEREDICTOS_FILTRO: readonly VeredictoChat[] = [
  'respondida',
  'sin_resultados',
  'fuera_de_scope',
  'escalar',
] as const

const ICONO_METRICA_CHATS = {
  total: { icono: <Ic.MessageCircle size={22} className="text-[var(--acento)]" />, fondo: 'bg-[var(--acento-claro)]' },
  conCitaPct: { icono: <Ic.CheckCircle size={22} className="text-emerald-700" />, fondo: 'bg-emerald-50' },
  escalados: { icono: <Ic.Warning size={22} className="text-rose-700" />, fondo: 'bg-rose-50' },
} as const

/**
 * Pestaña «Chats» del Panel interno (spec `supervision-chats`).
 *
 * Trae del BFF las tres métricas del rango (`/api/admin/chats/metricas`) y el
 * listado agregado por `chat_id` (`/api/admin/chats`), con filtros por
 * veredicto y rango de fechas. Al abrir un chat, `DetalleChatModal` pide el
 * hilo completo y lo pinta por turno. Todo con el patrón de accesibilidad de
 * la pestaña «Preguntas sin resolver» (métricas con etiqueta textual,
 * `th scope="col"`, objetivos táctiles ≥ 44×44 px, chip icono+texto).
 */
export function PanelChats({ idioma }: { idioma: Idioma }) {
  const { t, i18n } = useTranslation()
  const router = useRouter()

  // Filtros de la vista. `veredicto === null` = todos; `desde`/`hasta` vacíos =
  // el default del backend (últimos 30 días). Se mantienen entre renders para
  // que las métricas y la tabla usen exactamente el mismo criterio.
  const [veredicto, setVeredicto] = useState<VeredictoChat | null>(null)
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  // Los filtros aplicados solo cambian al pulsar el botón, para no disparar N
  // peticiones mientras la persona editora tipea.
  const [filtrosAplicados, setFiltrosAplicados] = useState<{ veredicto: VeredictoChat | null; desde: string; hasta: string }>({
    veredicto: null,
    desde: '',
    hasta: '',
  })

  const [metricas, setMetricas] = useState<ChatMetricas | null>(null)
  const [chats, setChats] = useState<ChatItem[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const [errorLista, setErrorLista] = useState<string | null>(null)
  const [errorMetricas, setErrorMetricas] = useState<string | null>(null)
  const [chatAbierto, setChatAbierto] = useState<string | null>(null)

  const alSesionExpirada = useCallback(() => {
    router.replace(rutas.login(idioma))
  }, [idioma, router])

  const cargarDatos = useCallback(async () => {
    setCargando(true)
    setErrorLista(null)
    setErrorMetricas(null)

    const rango = { desde: filtrosAplicados.desde || undefined, hasta: filtrosAplicados.hasta || undefined }
    const filtrosLista: FiltrosChats = {
      ...(filtrosAplicados.veredicto ? { veredicto: filtrosAplicados.veredicto } : {}),
      ...rango,
    }

    // Métricas y listado son independientes; se piden en paralelo.
    const [respMetricas, respLista] = await Promise.all([
      obtenerMetricasChats(rango).catch(() => null),
      listarChats(filtrosLista).catch(() => null),
    ])

    if (respMetricas === null) {
      setErrorMetricas(t('panelChats.errorMetricas'))
    } else if (respMetricas.ok) {
      setMetricas((await respMetricas.json()) as ChatMetricas)
    } else if (respMetricas.status === 401) {
      alSesionExpirada()
      return
    } else {
      setErrorMetricas(t('panelChats.errorMetricas'))
    }

    if (respLista === null) {
      setErrorLista(t('panelChats.errorCargar'))
      setChats([])
      setCursor(null)
    } else if (respLista.ok) {
      const cuerpo = (await respLista.json()) as { items: ChatItem[]; siguiente_cursor: string | null }
      setChats(cuerpo.items)
      setCursor(cuerpo.siguiente_cursor)
    } else if (respLista.status === 401) {
      alSesionExpirada()
      return
    } else {
      setErrorLista(t('panelChats.errorCargar'))
      setChats([])
      setCursor(null)
    }

    setCargando(false)
  }, [filtrosAplicados, alSesionExpirada, t])

  useEffect(() => {
    void cargarDatos()
  }, [cargarDatos])

  async function cargarMas() {
    if (!cursor) return
    const filtrosLista: FiltrosChats = {
      ...(filtrosAplicados.veredicto ? { veredicto: filtrosAplicados.veredicto } : {}),
      ...(filtrosAplicados.desde ? { desde: filtrosAplicados.desde } : {}),
      ...(filtrosAplicados.hasta ? { hasta: filtrosAplicados.hasta } : {}),
      cursor,
    }
    const resp = await listarChats(filtrosLista).catch(() => null)
    if (resp === null) {
      setErrorLista(t('panelChats.errorCargar'))
      return
    }
    if (resp.status === 401) {
      alSesionExpirada()
      return
    }
    if (!resp.ok) {
      setErrorLista(t('panelChats.errorCargar'))
      return
    }
    const cuerpo = (await resp.json()) as { items: ChatItem[]; siguiente_cursor: string | null }
    setChats(prev => [...prev, ...cuerpo.items])
    setCursor(cuerpo.siguiente_cursor)
  }

  function aplicarFiltros(evento: FormEvent) {
    evento.preventDefault()
    setFiltrosAplicados({ veredicto, desde, hasta })
  }

  function limpiarFiltros() {
    setVeredicto(null)
    setDesde('')
    setHasta('')
    setFiltrosAplicados({ veredicto: null, desde: '', hasta: '' })
  }

  const claves = ['total', 'conCitaPct', 'escalados'] as const
  type ClaveMetrica = (typeof claves)[number]
  const valorMetrica: Record<ClaveMetrica, string> = {
    total: metricas ? String(metricas.chats_total) : '—',
    conCitaPct: metricas ? `${metricas.chats_respondidos_con_cita_pct.toFixed(1)} %` : '—',
    escalados: metricas ? String(metricas.chats_escalados) : '—',
  }

  const columnas = ['chat', 'idioma', 'turnos', 'veredicto', 'ultima', 'accion'] as const
  const alineacion: Record<(typeof columnas)[number], string> = {
    chat: 'text-left', idioma: 'text-left', turnos: 'text-right', veredicto: 'text-left', ultima: 'text-left', accion: 'text-left',
  }

  return (
    <section aria-labelledby="chats-h2" className="space-y-6">
      <div>
        <h2 id="chats-h2" className="sr-only">
          {t('panelChats.titulo')}
        </h2>
        <p className="text-slate-600 text-sm">{t('panelChats.subtitulo')}</p>
      </div>

      {/* Métricas: mismo patrón que la pestaña KCS (icono + valor + etiqueta
          textual). El valor lleva sr-only con la etiqueta para que no dependa
          del color. */}
      <section aria-labelledby="chats-metricas-h">
        <h3 id="chats-metricas-h" className="sr-only">
          {t('panelChats.metricasAria')}
        </h3>
        {errorMetricas && (
          <p role="alert" className="mb-3 inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
            <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
            {errorMetricas}
          </p>
        )}
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {claves.map(clave => {
            const { icono, fondo } = ICONO_METRICA_CHATS[clave]
            const termino = t(`panelChats.metricas.${clave}`)
            const valor = valorMetrica[clave]
            const anuncio = clave === 'conCitaPct' && metricas
              ? `${t('panelChats.porcentajeAria', { valor: metricas.chats_respondidos_con_cita_pct.toFixed(1) })} — ${termino}`
              : `${valor} — ${termino}`
            return (
              <div key={clave} className="bg-white border border-slate-200 rounded-2xl p-5 flex items-start gap-4">
                <div className={`shrink-0 w-12 h-12 rounded-xl flex items-center justify-center ${fondo}`}>{icono}</div>
                <div>
                  <dt className="text-xs font-semibold text-slate-600 uppercase tracking-wide leading-snug">{termino}</dt>
                  <dd className="text-3xl font-bold text-slate-900 mt-1 leading-none">
                    <span className="sr-only">{anuncio}</span>
                    <span aria-hidden="true">{valor}</span>
                  </dd>
                  <p className="text-xs text-slate-500 mt-1">{t(`panelChats.metricas.${clave}Sub`)}</p>
                </div>
              </div>
            )
          })}
        </dl>
      </section>

      {/* Filtros: chip por veredicto (aria-pressed) + rango de fechas. */}
      <form onSubmit={aplicarFiltros} className="space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span id="chats-filtro-veredicto" className="text-sm font-medium text-slate-700">
            {t('panelChats.filtroVeredicto')}
          </span>
          <div className="flex items-center gap-2 flex-wrap" role="group" aria-labelledby="chats-filtro-veredicto">
            <button
              type="button"
              onClick={() => setVeredicto(null)}
              aria-pressed={veredicto === null}
              className={`px-3 rounded-full text-xs font-semibold border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                veredicto === null
                  ? 'bg-[var(--acento)] text-white border-[var(--acento)]'
                  : 'bg-white text-slate-700 border-slate-500 hover:border-[var(--acento)] hover:text-[var(--acento)]'
              }`}
            >
              {t('panelChats.filtroTodas')}
            </button>
            {VEREDICTOS_FILTRO.map(v => {
              const activo = veredicto === v
              return (
                <button
                  key={v}
                  type="button"
                  onClick={() => setVeredicto(v)}
                  aria-pressed={activo}
                  className={`px-3 rounded-full text-xs font-semibold border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                    activo
                      ? 'bg-[var(--acento)] text-white border-[var(--acento)]'
                      : 'bg-white text-slate-700 border-slate-500 hover:border-[var(--acento)] hover:text-[var(--acento)]'
                  }`}
                >
                  {t(`panelChats.veredictos.${v}`)}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label htmlFor="chats-desde" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelChats.filtroDesde')}
            </label>
            <input
              id="chats-desde"
              type="date"
              value={desde}
              onChange={e => setDesde(e.target.value)}
              className="px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
            />
          </div>
          <div>
            <label htmlFor="chats-hasta" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelChats.filtroHasta')}
            </label>
            <input
              id="chats-hasta"
              type="date"
              value={hasta}
              onChange={e => setHasta(e.target.value)}
              className="px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
            />
          </div>
          <button
            type="submit"
            className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
            style={{ background: 'var(--acento)' }}
          >
            {t('panelChats.aplicarFiltros')}
          </button>
          <button
            type="button"
            onClick={limpiarFiltros}
            className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          >
            {t('panelChats.limpiarFiltros')}
          </button>
        </div>
      </form>

      {/* Tabla del listado agregado por chat. */}
      <section aria-labelledby="chats-tabla-h">
        <h3 id="chats-tabla-h" className="sr-only">
          {t('panelChats.tablaTitulo')}
        </h3>
        {errorLista && (
          <p role="alert" className="mb-3 inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
            <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
            {errorLista}
          </p>
        )}

        <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
          {cargando ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t('panelChats.cargando')}</p>
          ) : chats.length === 0 ? (
            <p className="px-4 py-6 text-sm text-slate-600">{t('panelChats.vacio')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label={t('panelChats.tablaAria')}>
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {columnas.map(col => (
                      <th
                        key={col}
                        scope="col"
                        className={`px-4 py-3 text-xs font-bold text-slate-600 uppercase tracking-wider whitespace-nowrap ${alineacion[col]}`}
                      >
                        {t(`panelChats.columnas.${col}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {chats.map(chat => {
                    const ultima = new Date(chat.ultima_en).toLocaleString(i18n.language, {
                      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
                    })
                    const idCorto = chat.chat_id.length > 12 ? `${chat.chat_id.slice(0, 8)}…` : chat.chat_id
                    return (
                      <tr key={chat.chat_id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3.5 text-slate-800 font-mono text-xs">
                          <span className="sr-only">{chat.chat_id}</span>
                          <span aria-hidden="true">{idCorto}</span>
                        </td>
                        <td className="px-4 py-3.5 text-slate-700 uppercase text-xs">{chat.idioma}</td>
                        <td className="px-4 py-3.5 text-right tabular-nums text-slate-900 font-semibold">{chat.turnos}</td>
                        <td className="px-4 py-3.5">
                          <VeredictoChip veredicto={chat.ultimo_veredicto} />
                        </td>
                        <td className="px-4 py-3.5 text-slate-600 whitespace-nowrap text-xs">
                          <time dateTime={chat.ultima_en}>{ultima}</time>
                        </td>
                        <td className="px-4 py-3.5">
                          <button
                            type="button"
                            onClick={() => setChatAbierto(chat.chat_id)}
                            aria-label={t('panelChats.verDetalleAria', { chat: chat.chat_id })}
                            className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-[var(--acento-claro)] text-[var(--acento)] bg-[var(--acento-claro)] hover:border-[var(--acento)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px] whitespace-nowrap"
                          >
                            <Ic.Eye size={13} />
                            {t('panelChats.verDetalle')}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="px-4 py-3 border-t border-slate-200 text-xs text-slate-600 bg-slate-50/50 flex items-center justify-between gap-2 flex-wrap">
            <span>{t('panelChats.mostrando', { visibles: chats.length })}</span>
            {cursor && (
              <button
                type="button"
                onClick={() => void cargarMas()}
                className="inline-flex items-center gap-2 px-3 rounded-lg border border-slate-500 bg-white text-slate-700 text-xs font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
              >
                {t('panelChats.hayMas')}
              </button>
            )}
          </div>
        </div>
      </section>

      {chatAbierto && (
        <DetalleChatModal
          chatId={chatAbierto}
          onCerrar={() => setChatAbierto(null)}
          onSesionExpirada={alSesionExpirada}
        />
      )}
    </section>
  )
}
