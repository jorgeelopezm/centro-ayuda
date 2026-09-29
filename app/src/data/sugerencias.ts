/**
 * Cliente del panel para las sugerencias de artículo generadas con IA
 * (`/api/admin/sugerencias*`, spec `sugerencia-articulos-ia`). Mismo patrón que
 * `src/data/adminChats.ts`: devuelve `Response` sin interpretar para que cada
 * pantalla trate 401 → login y el resto de códigos por su cuenta. La cookie del
 * BFF viaja sola: el catch-all `app/app/api/admin/[...ruta]` ya cubre este
 * prefijo, propagando al backend el Bearer.
 *
 * "Aceptar" una sugerencia no vive aquí: reutiliza `guardarArticulo` de
 * `src/data/admin.ts` con el destino `desdeSugerencia`, porque es el mismo alta
 * bilingüe atómico que "Nuevo artículo" (mismo candado de campos, mismo 409 por
 * id duplicado).
 */

import { apiFetch } from '@/bff/apiFetch'
import type { TraduccionAdmin } from '@/data/admin'

/** Las tres fuentes que agrega el pipeline de sugerencias. */
export type FuenteSugerencia = 'chat_escalado' | 'pregunta_sin_resolver' | 'documentacion_rag'

/** Ciclo de vida de una sugerencia: nunca es pública hasta `aceptada`. */
export type EstadoSugerencia = 'pendiente' | 'aceptada' | 'descartada'

/** Candidato agregado de una fuente (`GET /api/admin/sugerencias/candidatos`). */
export interface Candidato {
  fuente: FuenteSugerencia
  referencia: string
  titulo_sugerido: string
  idioma: string
  prioridad: number
  ya_generada: boolean
}

export interface CandidatosResp {
  items: Candidato[]
}

/** Una cita del borrador, cruzada contra los fragmentos recuperados y el portal. */
export interface CitaSugerencia {
  n: number
  tipo: 'articulo' | 'documento' | string
  titulo: string
  slug: string
}

/** Fila de la cola de pendientes (`GET /api/admin/sugerencias`). */
export interface SugerenciaItem {
  id: string
  fuente: FuenteSugerencia
  referencia: string
  titulo: string
  estado: EstadoSugerencia
  creado_en: string
}

export interface SugerenciasResp {
  items: SugerenciaItem[]
}

/** Borrador bilingüe completo (`GET /api/admin/sugerencias/{id}`), para precargar el formulario. */
export interface SugerenciaDetalle {
  id: string
  portal_id: string
  fuente: FuenteSugerencia
  referencia: string
  estado: EstadoSugerencia
  es: TraduccionAdmin
  pt: TraduccionAdmin
  citas: CitaSugerencia[]
  proveedor_chat: string
  proveedor_traduccion: string
  modelo: string
  articulo_id: string | null
  creado_por: string
  creado_en: string
  resuelto_en: string | null
}

export function listarCandidatos(fuente?: FuenteSugerencia): Promise<Response> {
  return apiFetch(`/api/admin/sugerencias/candidatos${fuente ? `?fuente=${fuente}` : ''}`)
}

/** Dispara el pipeline de generación; idempotente mientras el candidato tenga una sugerencia `pendiente`. */
export function generarSugerencia(fuente: FuenteSugerencia, referencia: string): Promise<Response> {
  return apiFetch('/api/admin/sugerencias/generar', {
    method: 'POST',
    body: JSON.stringify({ fuente, referencia }),
  })
}

export function listarSugerencias(): Promise<Response> {
  return apiFetch('/api/admin/sugerencias')
}

export function obtenerSugerencia(id: string): Promise<Response> {
  return apiFetch(`/api/admin/sugerencias/${encodeURIComponent(id)}`)
}

/** Archiva la sugerencia sin publicar nada. */
export function descartarSugerencia(id: string): Promise<Response> {
  return apiFetch(`/api/admin/sugerencias/${encodeURIComponent(id)}/descartar`, { method: 'POST' })
}
