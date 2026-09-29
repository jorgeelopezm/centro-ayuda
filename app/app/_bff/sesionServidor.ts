import { cookies, headers } from 'next/headers'
import { COOKIE_ACCESS } from '@/bff/cookies'
import { cabecerasPortal } from '@/bff/portal'
import { BACKEND } from './backend'

export interface SesionServidor {
  email: string
  nivel: number
}

/**
 * Identidad de la sesión resuelta en el servidor, para las guardias del panel
 * (antes de emitir HTML). Lee el access token de la cookie y consulta la
 * autoridad —el backend (`/api/auth/me`)— en vez de descodificar el JWT en el
 * borde: así un usuario desactivado o de nivel insuficiente se detecta al
 * instante. La renovación con el refresh token la hace el `middleware` antes de
 * llegar aquí; si no hay access válido, no hay sesión.
 *
 * Reenvía el host del navegador en `X-Forwarded-Host` (multi-tenant): el backend
 * resuelve el portal por el host, y `/api/auth/me` depende de `portal_actual`. Sin
 * el host reenviado, el backend vería el origen interno (`127.0.0.1`), no resolvería
 * portal y respondería 404, que aquí se leería como "sin sesión" y rebotaría a login.
 */
export async function sesionActual(): Promise<SesionServidor | null> {
  const jar = await cookies()
  const access = jar.get(COOKIE_ACCESS)?.value
  if (!access) return null

  const resp = await fetch(`${BACKEND}/api/auth/me`, {
    headers: { authorization: `Bearer ${access}`, ...cabecerasPortal(await headers()) },
    cache: 'no-store',
  })
  if (!resp.ok) return null
  return (await resp.json()) as SesionServidor
}
