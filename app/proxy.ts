import { NextResponse, type NextRequest } from 'next/server'
import {
  COOKIE_ACCESS,
  COOKIE_REFRESH,
  MAX_AGE_ACCESS,
  MAX_AGE_REFRESH,
  opcionesBorrado,
  opcionesCookie,
} from '@/bff/cookies'
import { hostEntrante } from '@/bff/portal'
import { construirCSP } from '@/seguridad/csp'
import { backendRefresh } from './app/_bff/backend'

/** Redirección de la raíz `/` al idioma preferido del navegador (por defecto `es`). */
function redirigirRaiz(request: NextRequest): NextResponse {
  const aceptado = request.headers.get('accept-language')?.toLowerCase() ?? ''
  const idioma = aceptado.startsWith('pt') || aceptado.includes(',pt') ? 'pt' : 'es'
  return NextResponse.redirect(new URL(`/${idioma}`, request.url))
}

function aLogin(request: NextRequest, idioma: string): NextResponse {
  const res = NextResponse.redirect(new URL(`/${idioma}/login`, request.url))
  res.cookies.set(COOKIE_ACCESS, '', opcionesBorrado())
  res.cookies.set(COOKIE_REFRESH, '', opcionesBorrado())
  return res
}

/**
 * Guardia del panel en el borde, antes de emitir HTML (task 5.2):
 * - Con access token válido (la cookie caduca a la vez que el JWT) → sigue.
 * - Sin access pero con refresh → renueva contra el backend y reescribe cookies.
 * - Sin ninguno o con refresh inválido → redirige a `/{idioma}/login`.
 *
 * La comprobación de **nivel** (Administrador para gestión de usuarios) la hace el Server
 * Component consultando `/api/auth/me`: aquí no se descodifica el JWT.
 */
async function guardarPanel(
  request: NextRequest,
  idioma: string,
  requestHeaders: Headers,
): Promise<NextResponse> {
  const access = request.cookies.get(COOKIE_ACCESS)?.value
  const refresh = request.cookies.get(COOKIE_REFRESH)?.value

  if (access) return NextResponse.next({ request: { headers: requestHeaders } })
  if (!refresh) return aLogin(request, idioma)

  // El refresh también resuelve el portal por el host: se reenvía el del navegador.
  const renov = await backendRefresh(refresh, hostEntrante(request.headers))
  if (!renov.ok) return aLogin(request, idioma)

  const { access_token, refresh_token } = (await renov.json()) as {
    access_token: string
    refresh_token: string
  }
  const res = NextResponse.next({ request: { headers: requestHeaders } })
  res.cookies.set(COOKIE_ACCESS, access_token, opcionesCookie(MAX_AGE_ACCESS))
  res.cookies.set(COOKIE_REFRESH, refresh_token, opcionesCookie(MAX_AGE_REFRESH))
  return res
}

/**
 * Proxy del borde (Next 16 renombró el convenio `middleware` → `proxy`). Dos
 * responsabilidades:
 *
 * 1. **Content-Security-Policy con nonce por petición.** El nonce viaja en un
 *    header de petición (`x-nonce`) para que Next lo aplique a sus `<script>`,
 *    y en la respuesta como cabecera CSP. Se genera aquí (y no como cabecera
 *    estática en `next.config`) porque cambia en cada petición.
 * 2. **Guardia del panel** (solo rutas `/(es|pt)/panel*`) y redirección de la
 *    raíz. El resto de rutas solo reciben la CSP y siguen.
 *
 * Las demás cabeceras de seguridad (HSTS, nosniff, Referrer-Policy, …) son
 * estáticas y viven en `next.config.mjs` para cubrir también los recursos.
 */
export async function proxy(request: NextRequest): Promise<NextResponse> {
  const { pathname } = request.nextUrl

  const nonce = Buffer.from(crypto.randomUUID()).toString('base64')
  const csp = construirCSP(nonce)
  // Se copian las cabeceras entrantes (incluido `Host`) hacia el render: los Server
  // Components leen ese host con `next/headers` y lo reenvían al backend para resolver
  // el portal (task 3.2). El portal se resuelve por el host, no por la ruta ni el idioma.
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set('x-nonce', nonce)
  requestHeaders.set('content-security-policy', csp)

  let response: NextResponse
  if (pathname === '/') {
    response = redirigirRaiz(request)
  } else if (/^\/(es|pt)\/panel(?:\/|$)/.test(pathname)) {
    const idioma = pathname.split('/')[1] === 'pt' ? 'pt' : 'es'
    response = await guardarPanel(request, idioma, requestHeaders)
  } else {
    response = NextResponse.next({ request: { headers: requestHeaders } })
  }

  response.headers.set('content-security-policy', csp)
  return response
}

export const config = {
  // Todas las rutas salvo las del BFF (`/api`, que fija sus propias cookies), los
  // recursos internos de Next y el favicon: así la CSP con nonce cubre todo el
  // HTML renderizado sin envolver respuestas de API ni recursos estáticos.
  matcher: [{ source: '/((?!api|_next/static|_next/image|favicon.ico).*)' }],
}
