import { NextResponse, type NextRequest } from 'next/server'
import { CABECERA_PORTAL, hostEntrante } from '@/bff/portal'
import { BACKEND } from '../../../../_bff/backend'

/**
 * BFF del chat público: reenvía `POST /api/{idioma}/chat/consultar` al backend.
 *
 * A diferencia del proxy del panel (`api/admin/[...ruta]/route.ts`) esta ruta
 * es Anonymous: NO adjunta la cookie de sesión de admin. Lo único que reenvía
 * es el host del portal en `X-Forwarded-Host`, que es la única fuente del
 * tenant para el backend (`app/deps.py::portal_actual`).
 *
 * El BFF no interpreta el cuerpo: se reenvía tal cual (los guardarraíles —
 * longitud, límite de tasa, aislamiento por portal, validación de citas — los
 * aplica el backend, ver `api/app/routers/chat.py`). Si el cliente adjunta un
 * `portal_id` en el JSON, el backend lo ignora silenciosamente.
 */
export async function POST(
  request: NextRequest,
  ctx: { params: Promise<{ idioma: string }> },
): Promise<NextResponse> {
  const { idioma } = await ctx.params

  // Cota estructural: `es` o `pt`. Cualquier otra cosa la rechaza el backend
  // con 404, pero se corta aquí para no reenviar rutas inválidas al origen.
  if (idioma !== 'es' && idioma !== 'pt') {
    return NextResponse.json({ detail: 'Idioma no encontrado' }, { status: 404 })
  }

  const host = hostEntrante(request.headers)
  const cabeceras: Record<string, string> = {
    'content-type': request.headers.get('content-type') ?? 'application/json',
  }
  if (host) cabeceras[CABECERA_PORTAL] = host

  // IP real del cliente hacia el backend: sin esto el rate limit colapsa toda
  // la audiencia bajo la IP del proxy (Next → 127.0.0.1) y una consulta legítima
  // de cualquier visitante dispara denegaciones a todos los demás. El backend
  // solo confía en `X-Forwarded-For` cuando el peer inmediato está en la lista
  // de proxies confiables (ver `app/routers/chat.py::_ip_de`). Se prefiere el
  // primer valor de `X-Forwarded-For` entrante (lo pone el edge/CDN cuando lo
  // hay). En su defecto se lee `x-real-ip` (nginx clásico). Si no hay ninguna,
  // se omite y el backend cae a `request.client.host`.
  const ipCliente =
    request.headers.get('x-forwarded-for')?.split(',', 1)[0]?.trim() ||
    request.headers.get('x-real-ip') ||
    ''
  if (ipCliente) cabeceras['x-forwarded-for'] = ipCliente

  // Reenvío como bytes: el cuerpo puede ser cualquier UTF-8 (incluye caracteres
  // que `request.text()` recodifica sin problemas, pero mantener bytes evita
  // dobles decodificaciones y espeja el patrón de `reenviarConSesion`).
  const cuerpo = await request.arrayBuffer()

  const resp = await fetch(`${BACKEND}/api/${idioma}/chat/consultar`, {
    method: 'POST',
    headers: cabeceras,
    body: cuerpo,
    cache: 'no-store',
  })

  return new NextResponse(await resp.text(), {
    status: resp.status,
    headers: { 'content-type': resp.headers.get('content-type') ?? 'application/json' },
  })
}
