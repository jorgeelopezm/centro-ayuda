import { type NextRequest, type NextResponse } from 'next/server'
import { reenviarConSesion } from '../../../_bff/sesion'

/** Identidad de la sesión (`/api/auth/me`), reenviada con la cookie de sesión. */
export function GET(request: NextRequest): Promise<NextResponse> {
  return reenviarConSesion(request, '/api/auth/me')
}
