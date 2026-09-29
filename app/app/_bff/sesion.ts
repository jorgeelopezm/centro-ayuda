import { NextResponse, type NextRequest } from 'next/server'
import { cookies } from 'next/headers'
import {
  COOKIE_ACCESS,
  COOKIE_REFRESH,
  MAX_AGE_ACCESS,
  MAX_AGE_REFRESH,
  opcionesBorrado,
  opcionesCookie,
} from '@/bff/cookies'
import { CABECERA_PORTAL, hostEntrante } from '@/bff/portal'
import { BACKEND, backendRefresh } from './backend'

interface Sesion {
  access: string
  refresh: string
}

/** Escribe el par de cookies httpOnly de la sesión en la respuesta. */
export function fijarSesion(resp: NextResponse, sesion: Sesion): void {
  resp.cookies.set(COOKIE_ACCESS, sesion.access, opcionesCookie(MAX_AGE_ACCESS))
  resp.cookies.set(COOKIE_REFRESH, sesion.refresh, opcionesCookie(MAX_AGE_REFRESH))
}

/** Borra ambas cookies de sesión (cierre de sesión o 401 irrecuperable). */
export function limpiarSesion(resp: NextResponse): void {
  resp.cookies.set(COOKIE_ACCESS, '', opcionesBorrado())
  resp.cookies.set(COOKIE_REFRESH, '', opcionesBorrado())
}

// Códigos HTTP que, por RFC 9110, NO pueden llevar cuerpo. Undici valida esto
// al construir la `Response`: pasar un `texto` (aunque sea `""`) con status 204
// tira `TypeError: Response with null body status cannot have body`, que Next
// convierte en 500 antes de que la respuesta llegue al cliente. Se pasa `null`
// explícitamente para estos códigos (típicamente el 204 del DELETE).
const STATUS_SIN_CUERPO = new Set([101, 204, 205, 304])

// Cota del BFF para una respuesta del backend. Se fija POR ENCIMA del presupuesto
// del propio backend (generación de borrador 120 s + traducción 90 s, ver
// `api/app/servicios_ia.py`) para que, cuando algo falle, gane el error del backend
// —que dice la causa y lleva código de correlación— y no un corte ciego del BFF.
// Sin esta cota, el `fetch` heredaba el default de undici y podía quedarse colgado
// reteniendo la conexión del navegador.
const TIMEOUT_BFF_MS = 240_000

function respuestaDesde(backendResp: Response, texto: string): NextResponse {
  if (STATUS_SIN_CUERPO.has(backendResp.status)) {
    // Sin cuerpo ni content-type: RFC 9110 §6.4.1 (una respuesta 204 no lleva
    // cuerpo, y `content-type` sin cuerpo es semánticamente ambiguo).
    return new NextResponse(null, { status: backendResp.status })
  }
  return new NextResponse(texto, {
    status: backendResp.status,
    headers: { 'content-type': backendResp.headers.get('content-type') ?? 'application/json' },
  })
}

/**
 * Reenvía una petición del navegador al backend adjuntando el access token de la
 * cookie como `Authorization: Bearer`. Si el access falta o el backend responde
 * 401, intenta renovar con el refresh token (rotatorio) y reintenta una vez.
 *
 * Reglas: el BFF **no decide permisos** (propaga el 403 del backend tal cual);
 * ante un 401 irrecuperable borra las cookies; el token nunca vuelve al cliente.
 */
export async function reenviarConSesion(request: NextRequest, rutaBackend: string): Promise<NextResponse> {
  const jar = await cookies()
  const access = jar.get(COOKIE_ACCESS)?.value
  const refresh = jar.get(COOKIE_REFRESH)?.value

  const url = `${BACKEND}${rutaBackend}${request.nextUrl.search}`
  const metodo = request.method
  // El backend resuelve el portal por el host: se reenvía el host del navegador en
  // `X-Forwarded-Host` (el `Host` de la URL interna del backend no vale). Del host
  // entrante de confianza, no de un valor del cliente.
  const host = hostEntrante(request.headers)
  // Se reenvía como bytes (ArrayBuffer), no como texto: `request.text()` decodifica
  // en UTF-8 y corrompería un binario (p. ej. la subida del logotipo PNG/ICO). Para
  // los cuerpos JSON es indistinto (los mismos bytes con su `content-type`).
  const cuerpo = metodo === 'GET' || metodo === 'HEAD' ? undefined : await request.arrayBuffer()
  const tipo = request.headers.get('content-type') ?? undefined
  // `Content-Disposition` transporta el nombre de archivo en las subidas de
  // documentos (`src/data/admin.ts › subirDocumento`); si no se reenvía, el
  // backend cae al literal "documento" y la tabla del panel muestra ese
  // marcador en lugar del nombre real del PDF/DOCX/MD/TXT.
  const disposicion = request.headers.get('content-disposition') ?? undefined

  const llamar = (token?: string): Promise<Response> => {
    const headers: Record<string, string> = {}
    if (tipo) headers['content-type'] = tipo
    if (disposicion) headers['content-disposition'] = disposicion
    if (host) headers[CABECERA_PORTAL] = host
    if (token) headers.authorization = `Bearer ${token}`
    return fetch(url, {
      method: metodo,
      headers,
      body: cuerpo,
      cache: 'no-store',
      signal: AbortSignal.timeout(TIMEOUT_BFF_MS),
    })
  }

  try {
    let sesionNueva: Sesion | null = null
    let backendResp: Response | null = access ? await llamar(access) : null

    // Renueva si no había access token o si el backend lo rechazó (401).
    if ((backendResp === null || backendResp.status === 401) && refresh) {
      const renov = await backendRefresh(refresh, host)
      if (renov.ok) {
        const { access_token, refresh_token } = (await renov.json()) as {
          access_token: string
          refresh_token: string
        }
        sesionNueva = { access: access_token, refresh: refresh_token }
        backendResp = await llamar(access_token)
      } else {
        const fuera = NextResponse.json({ detail: 'No autenticado' }, { status: 401 })
        limpiarSesion(fuera)
        return fuera
      }
    }

    if (backendResp === null) {
      // Sin access token y sin refresh: nunca hubo sesión.
      return NextResponse.json({ detail: 'No autenticado' }, { status: 401 })
    }

    const out = respuestaDesde(backendResp, await backendResp.text())
    if (backendResp.status === 401) {
      limpiarSesion(out)
    } else if (sesionNueva) {
      fijarSesion(out, sesionNueva)
    }
    return out
  } catch (error) {
    // El backend no respondió (caído, conexión cortada) o agotó `TIMEOUT_BFF_MS`.
    // Sin este `catch`, la excepción escapaba del Route Handler y Next devolvía un
    // 500 opaco, indistinguible de un fallo de nuestro propio código.
    const agotado = error instanceof DOMException && error.name === 'TimeoutError'
    console.error(`[bff] ${metodo} ${rutaBackend} sin respuesta del backend:`, error)
    return NextResponse.json(
      {
        detail: agotado
          ? 'El servidor tardó demasiado en responder. Inténtalo de nuevo.'
          : 'No se pudo contactar con el servidor. Inténtalo de nuevo.',
      },
      { status: 504 },
    )
  }
}
