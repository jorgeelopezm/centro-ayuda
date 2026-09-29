import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { NivelAcceso } from '@/auth/nivel'
import { guardarUsuario, type UsuarioAdmin } from '@/data/admin'
import { Ic } from '@/components/iconos'

type Modo = 'crear' | 'editar'

/**
 * Alta y edición de un usuario administrable. Al crear, la contraseña es
 * obligatoria (mínimo 12 caracteres); al editar, se deja en blanco para no
 * cambiarla. El nivel se elige entre Editor y Administrador.
 */
export function UsuarioForm({
  modo,
  inicial,
  onCerrar,
  onGuardado,
}: {
  modo: Modo
  inicial?: UsuarioAdmin
  onCerrar: () => void
  onGuardado: (modo: Modo) => void
}) {
  const { t } = useTranslation()
  const [email, setEmail] = useState(inicial?.email ?? '')
  const [nivel, setNivel] = useState<number>(inicial?.nivel ?? NivelAcceso.EDITOR)
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      const destino =
        modo === 'crear' ? ({ tipo: 'crear' } as const) : ({ tipo: 'editar', usuarioId: inicial!.id } as const)
      const resp = await guardarUsuario({ email, nivel, password: password || undefined }, destino)
      if (resp.ok) {
        onGuardado(modo)
        return
      }
      // 409: correo en uso o la operación dejaría al sistema sin Administrador activo.
      setError(resp.status === 409 ? t('gestionUsuarios.errorConflicto') : t('gestionUsuarios.errorGuardar'))
    } catch {
      setError(t('gestionUsuarios.errorRed'))
    } finally {
      setEnviando(false)
    }
  }

  const idBase = modo === 'crear' ? 'nuevo' : `edit-${inicial?.id}`

  return (
    <form
      onSubmit={enviar}
      className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"
      aria-label={modo === 'crear' ? t('gestionUsuarios.nuevo') : t('gestionUsuarios.editarTitulo')}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor={`${idBase}-email`} className="block text-sm font-medium text-slate-700 mb-1">
            {t('gestionUsuarios.correo')}
          </label>
          <input
            id={`${idBase}-email`}
            type="email"
            required
            autoComplete="off"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          />
        </div>

        <div>
          <label htmlFor={`${idBase}-nivel`} className="block text-sm font-medium text-slate-700 mb-1">
            {t('gestionUsuarios.nivel')}
          </label>
          <select
            id={`${idBase}-nivel`}
            value={nivel}
            onChange={e => setNivel(Number(e.target.value))}
            className="w-full px-3 py-2.5 rounded-lg border border-slate-400 bg-white text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          >
            <option value={NivelAcceso.EDITOR}>{t('gestionUsuarios.nivelEditor')}</option>
            <option value={NivelAcceso.ADMINISTRADOR}>{t('gestionUsuarios.nivelAdministrador')}</option>
          </select>
        </div>
      </div>

      <div>
        <label htmlFor={`${idBase}-password`} className="block text-sm font-medium text-slate-700 mb-1">
          {t('gestionUsuarios.contrasena')}
        </label>
        <input
          id={`${idBase}-password`}
          type="password"
          required={modo === 'crear'}
          minLength={12}
          autoComplete="new-password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          aria-describedby={`${idBase}-password-ayuda`}
          className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
        />
        <p id={`${idBase}-password-ayuda`} className="text-xs text-slate-500 mt-1">
          {modo === 'crear' ? t('gestionUsuarios.contrasenaAyudaCrear') : t('gestionUsuarios.contrasenaAyudaEditar')}
        </p>
      </div>

      <div role="alert" aria-live="assertive" className="min-h-[1.25rem]">
        {error && (
          <p className="inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
            <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
            {error}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="submit"
          disabled={enviando}
          className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px] disabled:opacity-60"
          style={{ background: 'var(--acento)' }}
        >
          <Ic.CheckCircle size={15} />
          {enviando ? t('gestionUsuarios.guardando') : t('gestionUsuarios.guardar')}
        </button>
        <button
          type="button"
          onClick={onCerrar}
          className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
        >
          {t('gestionUsuarios.cancelar')}
        </button>
      </div>
    </form>
  )
}
