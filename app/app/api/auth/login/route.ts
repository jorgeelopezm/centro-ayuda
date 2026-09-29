import { NextResponse, type NextRequest } from 'next/server'
import { hostEntrante } from '@/bff/portal'
import { backendLogin } from '../../../_bff/backend'
import { fijarSesion } from '../../../_bff/sesion'

/**
 * Login del BFF. Envía las credenciales al backend, y si son válidas guarda el
 * par access/refresh en cookies httpOnly. **No devuelve el token en el cuerpo**:
 * el navegador nunca lo ve. Un 401 del backend se propaga tal cual.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  let email: unknown
  let password: unknown
  try {
    ;({ email, password } = await request.json())
  } catch {
    return NextResponse.json({ detail: 'Cuerpo inválido' }, { status: 400 })
  }
  if (typeof email !== 'string' || typeof password !== 'string') {
    return NextResponse.json({ detail: 'Correo y contraseña requeridos' }, { status: 400 })
  }

  const resp = await backendLogin(email, password, hostEntrante(request.headers))
  if (!resp.ok) {
    const texto = await resp.text()
    return new NextResponse(texto, {
      status: resp.status,
      headers: { 'content-type': resp.headers.get('content-type') ?? 'application/json' },
    })
  }

  const { access_token, refresh_token } = (await resp.json()) as {
    access_token: string
    refresh_token: string
  }
  const out = NextResponse.json({ ok: true })
  fijarSesion(out, { access: access_token, refresh: refresh_token })
  return out
}
