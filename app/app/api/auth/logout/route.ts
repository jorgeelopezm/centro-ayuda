import { NextResponse, type NextRequest } from 'next/server'
import { cookies } from 'next/headers'
import { COOKIE_REFRESH } from '@/bff/cookies'
import { hostEntrante } from '@/bff/portal'
import { backendLogout } from '../../../_bff/backend'
import { limpiarSesion } from '../../../_bff/sesion'

/**
 * Logout del BFF. Revoca la familia del refresh token en el backend (si hay) y
 * borra ambas cookies. Siempre responde 200: cerrar sesión no debe poder fallar.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const jar = await cookies()
  const refresh = jar.get(COOKIE_REFRESH)?.value
  if (refresh) {
    await backendLogout(refresh, hostEntrante(request.headers))
  }
  const out = NextResponse.json({ ok: true })
  limpiarSesion(out)
  return out
}
