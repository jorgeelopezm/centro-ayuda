import { headers } from 'next/headers'
import type { ContenidoIdioma, Idioma } from '@/types'
import { cabecerasPortal } from '@/bff/portal'

/**
 * Origen del backend FastAPI para las llamadas desde el servidor de Next. En
 * los Server Components no existe base para una URL relativa (`/api/...`), así
 * que se llama al backend directamente en vez de pasar por el `rewrite` de Next.
 */
// `127.0.0.1` en vez de `localhost`: el fetch de Node (undici) resuelve
// `localhost` a IPv6 `::1` primero, pero uvicorn suele escuchar solo en IPv4,
// y la conexión se rechazaría aunque el backend esté arriba.
const BACKEND = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'

/** Motivo por el que el portal del host no se pudo servir (estado accesible en la UI). */
export type MotivoPortal = 'no-encontrado' | 'no-disponible'

/**
 * El host de la petición no corresponde a un portal servible: o no existe
 * (`no-encontrado`, 404) o está suspendido (`no-disponible`, 503). La distingue de
 * un fallo genérico de la fuente para que la UI muestre el estado correcto (task 3.4)
 * y nunca sirva el contenido de otro portal.
 */
export class ErrorPortal extends Error {
  constructor(readonly motivo: MotivoPortal) {
    super(`Portal ${motivo}`)
    this.name = 'ErrorPortal'
  }
}

/**
 * Carga el contenido de un solo idioma desde el servidor. Sustituye a
 * `cargarContenidoLoader` (que traía ambos idiomas): cada pantalla obtiene solo
 * el idioma activo. El selector de idioma resuelve el otro bajo demanda.
 *
 * Reenvía el host del navegador al backend (`X-Forwarded-Host`) para que resuelva el
 * portal del host; un host desconocido (404) o un portal suspendido (503) se traducen a
 * `ErrorPortal`, que la capa de UI convierte en un estado accesible sin filtrar otro portal.
 */
export async function cargarContenidoServidor(idioma: Idioma): Promise<ContenidoIdioma> {
  const cabeceras = cabecerasPortal(await headers())
  const resp = await fetch(`${BACKEND}/api/${idioma}/contenido`, {
    cache: 'no-store',
    headers: cabeceras,
  })
  if (!resp.ok) {
    if (resp.status === 404) throw new ErrorPortal('no-encontrado')
    if (resp.status === 503) throw new ErrorPortal('no-disponible')
    throw new Error(`No se pudo cargar el contenido (${resp.status})`)
  }
  return (await resp.json()) as ContenidoIdioma
}
