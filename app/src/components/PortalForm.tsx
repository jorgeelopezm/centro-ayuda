import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { crearPortal, type PortalAdmin } from '@/data/admin'
import { Ic } from '@/components/iconos'

type Modo = 'crear' | 'ver'

const FORM_VACIO = { slug: '', nombreEmpresa: '', adminEmail: '', adminPassword: '' }

const CAMPO_DISABLED =
  'w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 disabled:bg-slate-100 disabled:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]'

/**
 * Alta de un portal (SuperAdmin) o su visor de solo lectura. `modo === 'ver'` NO
 * llama a ningún PUT (no existe): pinta los datos ya cargados en la tabla con todos
 * los campos `disabled` y un único botón para cerrar. Nunca muestra la contraseña
 * del Administrador: no se persiste en claro.
 */
export function PortalForm({
  modo,
  inicial,
  onCerrar,
  onGuardado,
}: {
  modo: Modo
  inicial?: PortalAdmin
  onCerrar: () => void
  onGuardado?: (empresa: string) => void
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState(FORM_VACIO)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const encabezadoRef = useRef<HTMLHeadingElement>(null)

  // El panel sustituye a la tabla/al formulario anterior en el mismo lugar del
  // DOM: sin esto, el foco de teclado/lector se pierde (cae a <body>) al abrir.
  useEffect(() => {
    encabezadoRef.current?.focus()
  }, [])

  async function crear(evento: FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      const resp = await crearPortal({
        slug: form.slug.trim(),
        nombreEmpresa: form.nombreEmpresa.trim(),
        adminEmail: form.adminEmail.trim(),
        adminPassword: form.adminPassword,
      })
      if (resp.ok) {
        onGuardado?.(form.nombreEmpresa.trim())
        return
      }
      if (resp.status === 409) {
        setError(t('gestionPortales.errorConflicto'))
      } else if (resp.status === 422) {
        setError(t('gestionPortales.errorValidacion'))
      } else {
        setError(t('gestionPortales.errorGuardar'))
      }
    } catch {
      setError(t('gestionPortales.errorRed'))
    } finally {
      setEnviando(false)
    }
  }

  if (modo === 'ver') {
    const portal = inicial!
    const estadoLabel = t(
      portal.estado === 'suspendido' ? 'gestionPortales.estadoSuspendido' : 'gestionPortales.estadoActivo',
    )
    return (
      <div
        className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"
        role="group"
        aria-labelledby="portal-ver-h"
      >
        <div>
          <h3
            id="portal-ver-h"
            ref={encabezadoRef}
            tabIndex={-1}
            className="text-sm font-semibold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded"
          >
            {t('gestionPortales.verTitulo', { empresa: portal.nombreEmpresa })}
          </h3>
          <p className="mt-1 text-xs text-slate-500">{t('gestionPortales.soloLectura')}</p>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="portal-ver-slug" className="block text-sm font-medium text-slate-700 mb-1">
              {t('gestionPortales.form.slug')}
            </label>
            <input id="portal-ver-slug" type="text" value={portal.slug} disabled className={CAMPO_DISABLED} />
          </div>
          <div>
            <label htmlFor="portal-ver-empresa" className="block text-sm font-medium text-slate-700 mb-1">
              {t('gestionPortales.form.nombreEmpresa')}
            </label>
            <input
              id="portal-ver-empresa"
              type="text"
              value={portal.nombreEmpresa}
              disabled
              className={CAMPO_DISABLED}
            />
          </div>
          <div>
            <label htmlFor="portal-ver-host" className="block text-sm font-medium text-slate-700 mb-1">
              {t('gestionPortales.form.host')}
            </label>
            <input id="portal-ver-host" type="text" value={portal.host ?? '—'} disabled className={CAMPO_DISABLED} />
          </div>
          <div>
            <label htmlFor="portal-ver-estado" className="block text-sm font-medium text-slate-700 mb-1">
              {t('gestionPortales.columnas.estado')}
            </label>
            <input id="portal-ver-estado" type="text" value={estadoLabel} disabled className={CAMPO_DISABLED} />
          </div>
          <div>
            <label htmlFor="portal-ver-admin-email" className="block text-sm font-medium text-slate-700 mb-1">
              {t('gestionPortales.form.adminEmail')}
            </label>
            <input
              id="portal-ver-admin-email"
              type="text"
              value={portal.adminEmail ?? '—'}
              disabled
              className={CAMPO_DISABLED}
            />
          </div>
          <div>
            <label htmlFor="portal-ver-creado" className="block text-sm font-medium text-slate-700 mb-1">
              {t('gestionPortales.form.creado')}
            </label>
            <input
              id="portal-ver-creado"
              type="text"
              value={new Date(portal.creado).toLocaleString()}
              disabled
              className={CAMPO_DISABLED}
            />
          </div>
        </div>
        <div className="flex items-center gap-2 justify-end">
          <button
            type="button"
            onClick={onCerrar}
            className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          >
            {t('gestionPortales.cerrar')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <form
      onSubmit={crear}
      className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"
      aria-labelledby="portal-form-h"
    >
      <h3
        id="portal-form-h"
        ref={encabezadoRef}
        tabIndex={-1}
        className="text-sm font-semibold text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded"
      >
        {t('gestionPortales.nuevo')}
      </h3>
      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="portal-slug" className="block text-sm font-medium text-slate-700 mb-1">
            {t('gestionPortales.form.slug')}
          </label>
          <input
            id="portal-slug"
            type="text"
            required
            value={form.slug}
            onChange={e => setForm({ ...form, slug: e.target.value })}
            aria-describedby="portal-slug-ayuda"
            autoComplete="off"
            pattern="[a-z0-9]([a-z0-9-]*[a-z0-9])?"
            className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          />
          <p id="portal-slug-ayuda" className="mt-1 text-xs text-slate-500">
            {t('gestionPortales.form.slugAyuda')}
          </p>
        </div>
        <div>
          <label htmlFor="portal-empresa" className="block text-sm font-medium text-slate-700 mb-1">
            {t('gestionPortales.form.nombreEmpresa')}
          </label>
          <input
            id="portal-empresa"
            type="text"
            required
            value={form.nombreEmpresa}
            onChange={e => setForm({ ...form, nombreEmpresa: e.target.value })}
            className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          />
        </div>
        <div>
          <label htmlFor="portal-admin-email" className="block text-sm font-medium text-slate-700 mb-1">
            {t('gestionPortales.form.adminEmail')}
          </label>
          <input
            id="portal-admin-email"
            type="email"
            required
            value={form.adminEmail}
            onChange={e => setForm({ ...form, adminEmail: e.target.value })}
            autoComplete="off"
            className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          />
        </div>
        <div>
          <label htmlFor="portal-admin-pass" className="block text-sm font-medium text-slate-700 mb-1">
            {t('gestionPortales.form.adminPassword')}
          </label>
          <input
            id="portal-admin-pass"
            type="password"
            required
            minLength={12}
            value={form.adminPassword}
            onChange={e => setForm({ ...form, adminPassword: e.target.value })}
            autoComplete="new-password"
            aria-describedby="portal-admin-pass-ayuda"
            className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          />
          <p id="portal-admin-pass-ayuda" className="mt-1 text-xs text-slate-500">
            {t('gestionPortales.form.adminPasswordAyuda')}
          </p>
        </div>
      </div>

      <div role="alert" aria-live="assertive" className="min-h-[1.25rem]">
        {error && (
          <p className="inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
            <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
            {error}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2 justify-end flex-wrap">
        <button
          type="button"
          onClick={onCerrar}
          className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-400 bg-white text-slate-800 text-sm font-semibold hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
        >
          <Ic.X size={15} />
          {t('gestionPortales.cancelar')}
        </button>
        <button
          type="submit"
          disabled={enviando}
          className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px] disabled:opacity-60"
          style={{ background: 'var(--acento)' }}
        >
          <Ic.Save size={15} />
          {enviando ? t('gestionPortales.creando') : t('gestionPortales.crear')}
        </button>
      </div>
    </form>
  )
}
