import { NextResponse, type NextRequest } from 'next/server'
import { reenviarConSesion } from '../../../_bff/sesion'

/**
 * Un segmento de recorrido (`.`, `..`) o con separadores incrustados sacaría la
 * URL de `/api/admin/*` al normalizarla `fetch`, dirigiendo el `Bearer` de la
 * sesión a otro endpoint del backend. El backend reautoriza cada ruta, así que
 * es defensa en profundidad, pero se rechaza en el borde: ninguna ruta legítima
 * del panel usa estos segmentos. (`encodeURIComponent` no vale: no escapa `.`.)
 */
function rutaSegura(ruta: string[]): boolean {
  return ruta.every(s => s !== '' && s !== '.' && s !== '..' && !s.includes('/') && !s.includes('\\'))
}

/**
 * Proxy del panel: cualquier `/api/admin/*` se reenvía al backend con el access
 * token de la cookie. El BFF custodia la credencial; **la autorización real (403
 * por nivel) la decide FastAPI** y aquí solo se propaga. Cubre los métodos que
 * usa la API de administración (`src/data/admin.ts`).
 */
async function proxy(
  request: NextRequest,
  ctx: { params: Promise<{ ruta: string[] }> },
): Promise<NextResponse> {
  const { ruta } = await ctx.params
  if (!rutaSegura(ruta)) return NextResponse.json({ detail: 'Ruta inválida' }, { status: 400 })
  return reenviarConSesion(request, `/api/admin/${ruta.join('/')}`)
}

export const GET = proxy
export const POST = proxy
export const PUT = proxy
export const DELETE = proxy
