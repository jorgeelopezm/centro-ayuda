import { NextResponse, type NextRequest } from 'next/server'
import { CABECERA_PORTAL, hostEntrante } from '@/bff/portal'
import { BACKEND } from '../../../_bff/backend'

/**
 * Contenido público por idioma para las **peticiones de cliente** (el selector de idioma
 * en un artículo pide el otro idioma bajo demanda). El SSR no pasa por aquí: usa
 * `src/data/servidor.ts` directamente.
 *
 * Reenvía `GET /api/{idioma}/contenido` al backend con el host del portal en
 * `X-Forwarded-Host`, para que resuelva el contenido **del portal** del host. Sustituye al
 * `rewrite` de `next.config`, que no permite fijar esa cabecera y con el que el contenido
 * podría resolverse a otro portal (o a ninguno). Público, sin sesión.
 */
export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ idioma: string }> },
): Promise<NextResponse> {
  const { idioma } = await ctx.params
  const host = hostEntrante(request.headers)
  const cabeceras: Record<string, string> = {}
  if (host) cabeceras[CABECERA_PORTAL] = host

  const resp = await fetch(`${BACKEND}/api/${idioma}/contenido`, {
    headers: cabeceras,
    cache: 'no-store',
  })
  // Se propaga cuerpo y estado tal cual: el cliente reacciona a su código (el backend
  // responde 404 para un idioma o un host desconocidos, y el selector cae con elegancia).
  return new NextResponse(await resp.text(), {
    status: resp.status,
    headers: { 'content-type': resp.headers.get('content-type') ?? 'application/json' },
  })
}
