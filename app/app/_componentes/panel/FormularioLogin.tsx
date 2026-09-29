'use client'

import { useState, type FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'

/**
 * Inicio de sesión del administrador. Envía las credenciales al BFF
 * (`POST /api/auth/login`), que fija las cookies httpOnly; el token nunca llega
 * al cliente. Al entrar, navega al panel y refresca para que la guardia de
 * servidor vea ya la sesión.
 */
export function FormularioLogin({ idioma }: { idioma: Idioma }) {
  const t = traducir(idioma)
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function alEnviar(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        credentials: 'same-origin',
      })
      if (!resp.ok) {
        setError(t('login.errorCredenciales'))
        return
      }
      router.replace(rutas.panel(idioma))
      router.refresh()
    } catch {
      setError(t('login.errorRed'))
    } finally {
      setEnviando(false)
    }
  }

  const claseCampo =
    'w-full px-3 py-2.5 rounded-lg border border-slate-500 bg-white text-slate-900 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:border-transparent'

  return (
    <main id="main-content" tabIndex={-1} className="min-h-[70vh] flex items-center justify-center px-4 py-12 focus:outline-none">
      <div className="w-full max-w-sm">
        <div className="text-center mb-6">
          <div className="mx-auto w-12 h-12 rounded-xl bg-[var(--acento-claro)] flex items-center justify-center mb-3">
            <Ic.Lock size={22} className="text-[var(--acento)]" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'var(--font-serif), serif' }}>
            {t('login.titulo')}
          </h1>
          <p className="text-slate-600 text-sm mt-1">{t('login.subtitulo')}</p>
        </div>

        <form onSubmit={alEnviar} noValidate className="bg-white border border-slate-200 rounded-2xl p-6 space-y-4">
          <div role="alert" aria-live="assertive" className="min-h-[1.25rem]">
            {error && (
              <p className="flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
                <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
                {error}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="login-email" className="block text-sm font-medium text-slate-700 mb-1.5">
              {t('login.correo')}
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              className={claseCampo}
            />
          </div>

          <div>
            <label htmlFor="login-password" className="block text-sm font-medium text-slate-700 mb-1.5">
              {t('login.contrasena')}
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              className={claseCampo}
            />
          </div>

          <button
            type="submit"
            disabled={enviando}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] disabled:opacity-60 min-h-[44px]"
            style={{ background: 'var(--acento)' }}
          >
            {enviando ? <Ic.Loader size={16} className="animate-spin motion-reduce:animate-none" /> : <Ic.Lock size={16} />}
            {enviando ? t('login.entrando') : t('login.entrar')}
          </button>
        </form>
      </div>
    </main>
  )
}
