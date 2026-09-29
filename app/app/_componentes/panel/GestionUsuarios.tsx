'use client'

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { Idioma } from '@/types'
import { NivelAcceso } from '@/auth/nivel'
import { activarUsuario, desactivarUsuario, listarUsuarios, type UsuarioAdmin } from '@/data/admin'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'
import { UsuarioForm } from '@/components/UsuarioForm'

type FormState = { modo: 'crear' | 'editar'; inicial?: UsuarioAdmin }

/**
 * Gestión de usuarios (solo Administrador). La ruta ya está protegida por el Server
 * Component (nivel Administrador); aun así, cada operación la vuelve a autorizar el backend.
 */
export function GestionUsuarios({ idioma }: { idioma: Idioma }) {
  const { t } = useTranslation()
  const router = useRouter()

  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([])
  const [formulario, setFormulario] = useState<FormState | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function cargar() {
    const resp = await listarUsuarios()
    if (resp.ok) {
      setUsuarios((await resp.json()) as UsuarioAdmin[])
      setError(null)
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else {
      setError(t('gestionUsuarios.errorCargar'))
    }
  }

  useEffect(() => {
    void cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idioma])

  async function cambiarEstado(usuario: UsuarioAdmin) {
    setError(null)
    if (usuario.activo && !window.confirm(t('gestionUsuarios.confirmarDesactivar', { correo: usuario.email }))) {
      return
    }
    const resp = usuario.activo ? await desactivarUsuario(usuario.id) : await activarUsuario(usuario.id)
    if (resp.ok) {
      setAviso(t(usuario.activo ? 'gestionUsuarios.desactivado' : 'gestionUsuarios.activado'))
      await cargar()
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else {
      setError(resp.status === 409 ? t('gestionUsuarios.errorSalvaguarda') : t('gestionUsuarios.errorGuardar'))
    }
  }

  function alGuardado(modo: 'crear' | 'editar') {
    setFormulario(null)
    setAviso(t(modo === 'crear' ? 'gestionUsuarios.creado' : 'gestionUsuarios.actualizado'))
    void cargar()
  }

  const columnas = ['correo', 'nivel', 'estado', 'accion'] as const

  return (
    <main id="main-content" tabIndex={-1} className="focus:outline-none">
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          <Link
            href={rutas.panel(idioma)}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--acento)] hover:text-[var(--acento-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded min-h-[44px]"
          >
            <Ic.ArrowLeft size={15} />
            {t('gestionUsuarios.volver')}
          </Link>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--acento)] uppercase tracking-widest mt-2 mb-1">
            <Ic.User size={14} />
            {t('gestionUsuarios.seccion')}
          </div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'var(--font-serif), serif' }}>
            {t('gestionUsuarios.titulo')}
          </h1>
          <p className="text-slate-600 text-sm mt-1">{t('gestionUsuarios.subtitulo')}</p>
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
          <h2 className="text-xl font-semibold text-slate-900">{t('gestionUsuarios.lista')}</h2>
          {!formulario && (
            <button
              type="button"
              onClick={() => {
                setFormulario({ modo: 'crear' })
                setAviso(null)
              }}
              className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
              style={{ background: 'var(--acento)' }}
            >
              <Ic.Plus size={15} />
              {t('gestionUsuarios.nuevo')}
            </button>
          )}
        </div>

        {formulario ? (
          <UsuarioForm
            modo={formulario.modo}
            inicial={formulario.inicial}
            onCerrar={() => setFormulario(null)}
            onGuardado={alGuardado}
          />
        ) : (
          <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label={t('gestionUsuarios.tablaAria')}>
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50">
                    {columnas.map(columna => (
                      <th
                        key={columna}
                        scope="col"
                        className="px-4 py-3 text-left text-xs font-bold text-slate-600 uppercase tracking-wider whitespace-nowrap"
                      >
                        {t(`gestionUsuarios.columnas.${columna}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {usuarios.map(usuario => {
                    const esAdministradorUsuario = usuario.nivel >= NivelAcceso.ADMINISTRADOR
                    return (
                      <tr key={usuario.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-4 py-3.5 text-slate-800 font-medium">{usuario.email}</td>
                        <td className="px-4 py-3.5">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-slate-300 text-slate-700 bg-slate-50">
                            {esAdministradorUsuario && <Ic.Shield size={12} />}
                            {t(esAdministradorUsuario ? 'gestionUsuarios.nivelAdministrador' : 'gestionUsuarios.nivelEditor')}
                          </span>
                        </td>
                        <td className="px-4 py-3.5">
                          {usuario.activo ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-emerald-200 text-emerald-800 bg-emerald-50">
                              <Ic.CheckCircle size={12} className="text-emerald-700" />
                              {t('gestionUsuarios.estadoActivo')}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-slate-300 text-slate-600 bg-slate-100">
                              <Ic.X size={12} />
                              {t('gestionUsuarios.estadoInactivo')}
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <button
                              type="button"
                              onClick={() => {
                                setFormulario({ modo: 'editar', inicial: usuario })
                                setAviso(null)
                              }}
                              aria-label={t('gestionUsuarios.editarAria', { correo: usuario.email })}
                              className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-slate-500 text-slate-700 bg-white hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                            >
                              <Ic.Edit size={14} />
                              {t('gestionUsuarios.editar')}
                            </button>
                            <button
                              type="button"
                              onClick={() => cambiarEstado(usuario)}
                              aria-label={t(
                                usuario.activo ? 'gestionUsuarios.desactivarAria' : 'gestionUsuarios.activarAria',
                                { correo: usuario.email },
                              )}
                              className={`inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                                usuario.activo
                                  ? 'border-red-200 text-red-800 bg-red-50 hover:bg-red-100'
                                  : 'border-emerald-200 text-emerald-800 bg-emerald-50 hover:bg-emerald-100'
                              }`}
                            >
                              {usuario.activo ? <Ic.X size={14} /> : <Ic.CheckCircle size={14} />}
                              {t(usuario.activo ? 'gestionUsuarios.desactivar' : 'gestionUsuarios.activar')}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {usuarios.length === 0 && (
              <p className="px-4 py-6 text-sm text-slate-600">{t('gestionUsuarios.vacio')}</p>
            )}
          </div>
        )}
      </div>
    </main>
  )
}
