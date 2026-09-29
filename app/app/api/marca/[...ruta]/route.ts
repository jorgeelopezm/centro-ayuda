import { NextResponse, type NextRequest } from 'next/server'
import { CABECERA_PORTAL, hostEntrante } from '@/bff/portal'
import { BACKEND } from '../../../_bff/backend'

/**
 * Proxy público de la marca (logotipo/favicon). Reenvía `GET /api/marca/*` al backend
 * con el host del portal en `X-Forwarded-Host`, para que resuelva **de qué portal** servir
 * el logo. Sustituye al `rewrite` de `next.config`: un rewrite externo no permite fijar esa
 * cabecera y Next no garantiza reenviar el `Host` original, así que el logo podría caer en
 * «portal no encontrado». Aquí el reenvío es explícito y determinista.
 *
 * Sin sesión: la marca es pública (como el nombre de empresa y la paleta). Se propaga el
 * binario tal cual con sus cabeceras de tipo/seguridad; el host se toma del entrante de
 * confianza, nunca de un valor del cliente.
 */

/** Rechaza segmentos de recorrido: ninguna ruta legítima de marca los usa. */
function rutaSegura(ruta: string[]): boolean {
  return ruta.every(s => s !== '' && s !== '.' && s !== '..' && !s.includes('/') && !s.includes('\\'))
}

// Cabeceras del binario que se propagan del backend al navegador (tipo real + defensa).
const CABECERAS_PROPAGADAS = [
  'content-type',
  'content-disposition',
  'content-security-policy',
  'x-content-type-options',
  'cache-control',
]

export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ ruta: string[] }> },
): Promise<NextResponse> {
  const { ruta } = await ctx.params
  if (!rutaSegura(ruta)) return NextResponse.json({ detail: 'Ruta inválida' }, { status: 400 })

  const host = hostEntrante(request.headers)
  const cabeceras: Record<string, string> = {}
  if (host) cabeceras[CABECERA_PORTAL] = host

  const resp = await fetch(`${BACKEND}/api/marca/${ruta.join('/')}`, {
    headers: cabeceras,
    cache: 'no-store',
  })

  // 404 (sin logo) y demás estados se propagan sin cuerpo binario; para 200 se reenvían
  // los bytes tal cual (no `text()`, que corrompería el binario).
  const cuerpo = resp.ok ? await resp.arrayBuffer() : null
  const out = new NextResponse(cuerpo, { status: resp.status })
  for (const h of CABECERAS_PROPAGADAS) {
    const valor = resp.headers.get(h)
    if (valor) out.headers.set(h, valor)
  }
  return out
}
