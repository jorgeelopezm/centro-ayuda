'use client'

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { Idioma } from '@/types'
import { listarPortales, reactivarPortal, suspenderPortal, type PortalAdmin } from '@/data/admin'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'
import { PortalForm } from '@/components/PortalForm'

type FormState = { modo: 'crear' } | { modo: 'ver'; inicial: PortalAdmin }

/**
 * Gestión de portales (solo SuperAdmin). La ruta ya está protegida por el Server Component
 * (nivel SuperAdmin); aun así, cada operación la vuelve a autorizar el backend. Lista los
 * portales, da de alta uno nuevo con su Administrador y los suspende/reactiva (reversible,
 * sin borrar datos). El portal de plataforma no aparece: no es gestionable.
 */
export function GestionPortales({ idioma }: { idioma: Idioma }) {
  const { t } = useTranslation()
  const router = useRouter()

  const [portales, setPortales] = useState<PortalAdmin[]>([])
  const [form, setForm] = useState<FormState | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Id del botón que abrió el panel (fila o "+ Nuevo portal"): al cerrarlo, la
  // tabla se remonta con nodos nuevos, así que se recupera por id, no por ref.
  const [disparadorId, setDisparadorId] = useState<string | null>(null)

  useEffect(() => {
    if (form === null && disparadorId) {
      document.getElementById(disparadorId)?.focus()
      setDisparadorId(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form])

  async function cargar() {
    const resp = await listarPortales()
    if (resp.ok) {
      setPortales((await resp.json()) as PortalAdmin[])
      setError(null)
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else {
      setError(t('gestionPortales.errorCargar'))
    }
  }

  useEffect(() => {
    void cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idioma])

  async function alGuardado(empresa: string) {
    setForm(null)
    setAviso(t('gestionPortales.creado', { empresa }))
    await cargar()
  }

  async function cambiarEstado(portal: PortalAdmin) {
    setError(null)
    const suspendido = portal.estado === 'suspendido'
    if (!suspendido && !window.confirm(t('gestionPortales.confirmarSuspender', { empresa: portal.nombreEmpresa }))) {
      return
    }
    const resp = suspendido ? await reactivarPortal(portal.id) : await suspenderPortal(portal.id)
    if (resp.ok) {
      setAviso(t(suspendido ? 'gestionPortales.reactivado' : 'gestionPortales.suspendido'))
      await cargar()
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else {
      setError(t('gestionPortales.errorGuardar'))
    }
  }

  const columnas = ['portal', 'host', 'estado', 'accion'] as const

  return (
    <main id="main-content" tabIndex={-1} className="focus:outline-none">
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          <Link
            href={rutas.panel(idioma)}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--acento)] hover:text-[var(--acento-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded min-h-[44px]"
          >
            <Ic.ArrowLeft size={15} />
            {t('gestionPortales.volver')}
          </Link>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--acento)] uppercase tracking-widest mt-2 mb-1">
            <Ic.Shield size={14} />
            {t('gestionPortales.seccion')}
          </div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'var(--font-serif), serif' }}>
            {t('gestionPortales.titulo')}
          </h1>
          <p className="text-slate-600 text-sm mt-1">{t('gestionPortales.subtitulo')}</p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <div role="status" aria-live="polite" className="min-h-[1.5rem]">
          {aviso && (
            <p className="inline-flex items-center gap-2 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-2 rounded-lg">
              <Ic.CheckCircle size={15} className="text-emerald-700 shrink-0" />
              {aviso}
            </p>
          )}
        </div>
        <div role="alert" aria-live="assertive" className="min-h-[1.25rem]">
          {error && (
            <p className="inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
              <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2 className="text-xl font-semibold text-slate-900">{t('gestionPortales.lista')}</h2>
          {!form && (
            <button
              type="button"
              id="portal-nuevo-btn"
              onClick={() => {
                setDisparadorId('portal-nuevo-btn')
                setForm({ modo: 'crear' })
                setAviso(null)
              }}
              className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
              style={{ background: 'var(--acento)' }}
            >
              <Ic.Plus size={15} />
              {t('gestionPortales.nuevo')}
            </button>
          )}
        </div>

        {form ? (
          <PortalForm
            modo={form.modo}
            inicial={form.modo === 'ver' ? form.inicial : undefined}
            onCerrar={() => setForm(null)}
            onGuardado={alGuardado}
          />
        ) : (
          <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label={t('gestionPortales.tablaAria')}>
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {columnas.map(columna => (
                      <th
                        key={columna}
                        scope="col"
                        className="px-4 py-3 text-left text-xs font-bold text-slate-600 uppercase tracking-wider whitespace-nowrap"
                      >
                        {t(`gestionPortales.columnas.${columna}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {portales.map(portal => {
                    const suspendido = portal.estado === 'suspendido'
                    return (
                      <tr key={portal.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3.5 text-slate-800 font-medium">
                          {portal.nombreEmpresa}
                          <span className="text-slate-400 font-normal"> · {portal.slug}</span>
                        </td>
                        <td className="px-4 py-3.5 text-slate-600 font-mono text-xs">{portal.host ?? '—'}</td>
                        <td className="px-4 py-3.5">
                          {suspendido ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-amber-300 text-amber-800 bg-amber-50">
                              <Ic.AlertCircle size={12} className="text-amber-700" />
                              {t('gestionPortales.estadoSuspendido')}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-emerald-200 text-emerald-800 bg-emerald-50">
                              <Ic.CheckCircle size={12} className="text-emerald-700" />
                              {t('gestionPortales.estadoActivo')}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <button
                              type="button"
                              id={`portal-ver-btn-${portal.id}`}
                              onClick={() => {
                                setDisparadorId(`portal-ver-btn-${portal.id}`)
                                setForm({ modo: 'ver', inicial: portal })
                                setAviso(null)
                              }}
                              aria-label={t('gestionPortales.editarAria', { empresa: portal.nombreEmpresa })}
                              className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-slate-500 text-slate-700 bg-white hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                            >
                              <Ic.Eye size={14} />
                              {t('gestionPortales.editar')}
                            </button>
                            <button
                              type="button"
                              onClick={() => cambiarEstado(portal)}
                              aria-label={t(
                                suspendido ? 'gestionPortales.reactivarAria' : 'gestionPortales.suspenderAria',
                                { empresa: portal.nombreEmpresa },
                              )}
                              className={`inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                                suspendido
                                  ? 'border-emerald-200 text-emerald-800 bg-emerald-50 hover:bg-emerald-100'
                                  : 'border-amber-300 text-amber-800 bg-amber-50 hover:bg-amber-100'
                              }`}
                            >
                              {suspendido ? <Ic.CheckCircle size={14} /> : <Ic.X size={14} />}
                              {t(suspendido ? 'gestionPortales.reactivar' : 'gestionPortales.suspender')}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {portales.length === 0 && (
              <p className="px-4 py-6 text-sm text-slate-600">{t('gestionPortales.vacio')}</p>
            )}
          </div>
        )}
      </div>
    </main>
  )
}
