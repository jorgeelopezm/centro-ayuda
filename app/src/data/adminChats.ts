/**
 * Cliente del panel para los endpoints de supervisión de chats
 * (`/api/admin/chats*`). Mantiene la misma forma que `src/data/admin.ts`:
 * devuelve `Response` sin interpretar para que cada pantalla trate 401 → login
 * y el resto de códigos por su cuenta. La cookie del BFF viaja sola: el
 * catch-all `app/app/api/admin/[...ruta]` propaga al backend el Bearer.
 */

import { apiFetch } from '@/bff/apiFetch'

/** Los cuatro veredictos del pipeline del chat (spec `chat-generativo-rag`). */
export type VeredictoChat = 'respondida' | 'sin_resultados' | 'fuera_de_scope' | 'escalar'

/** Una cita del asistente tal como se persiste en `chat_interaccion.citas`. */
export interface CitaChat {
  n: number
  tipo: 'articulo' | 'documento' | string
  titulo: string
  slug: string | null
}

/** Una fila del listado agregado por `chat_id` (`GET /api/admin/chats`). */
export interface ChatItem {
  chat_id: string
  portal_id: string
  idioma: string
  turnos: number
  ultimo_veredicto: VeredictoChat
  creado_en: string
  ultima_en: string
}

export interface ChatListaResp {
  items: ChatItem[]
  siguiente_cursor: string | null
}

/** Un turno del hilo (`GET /api/admin/chats/{chat_id}`). */
export interface ChatInteraccion {
  id: string
  chat_id: string
  portal_id: string
  turno: number
  idioma: string
  consulta: string
  veredicto: VeredictoChat
  mensaje: string
  citas: CitaChat[]
  razon_escalamiento: string | null
  latencia_ms: number
  tokens_entrada: number | null
  tokens_salida: number | null
  proveedor: string
  modelo: string
  creado_en: string
}

export interface ChatDetalle {
  chat_id: string
  portal_id: string
  interacciones: ChatInteraccion[]
}

/** Respuesta de `GET /api/admin/chats/metricas`. */
export interface ChatMetricas {
  chats_total: number
  chats_respondidos_con_cita_pct: number
  chats_escalados: number
  desde: string
  hasta: string
}

/** Filtros aceptados por el listado. Todos opcionales. */
export interface FiltrosChats {
  veredicto?: VeredictoChat
  desde?: string
  hasta?: string
  limit?: number
  cursor?: string
  // Índice de tipo: sin él, `FiltrosChats` no es asignable a
  // `Record<string, string | number | undefined>` en `construirQuery`.
  [clave: string]: string | number | undefined
}

function construirQuery(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams()
  for (const [clave, valor] of Object.entries(params)) {
    if (valor === undefined || valor === '') continue
    usp.set(clave, String(valor))
  }
  const cadena = usp.toString()
  return cadena ? `?${cadena}` : ''
}

export function listarChats(filtros: FiltrosChats = {}): Promise<Response> {
  return apiFetch(`/api/admin/chats${construirQuery(filtros)}`)
}

export function obtenerChat(chatId: string): Promise<Response> {
  return apiFetch(`/api/admin/chats/${encodeURIComponent(chatId)}`)
}

export function obtenerMetricasChats(
  rango: { desde?: string; hasta?: string } = {},
): Promise<Response> {
  return apiFetch(`/api/admin/chats/metricas${construirQuery(rango)}`)
}
