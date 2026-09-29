/**
 * Cliente del chat público y utilidades de serialización.
 *
 * El widget invoca `consultarChat` contra el BFF de Next (`/api/{idioma}/chat/consultar`),
 * que reenvía al backend con el host del portal. Los tipos de este módulo son el
 * contrato del BFF: mapean el `ChatConsultaOut` de FastAPI (ver `api/app/schemas.py`).
 *
 * `serializarConversacion` devuelve un texto plano listo para el `mailto:` de
 * escalamiento (y, más adelante, para el formulario de soporte de
 * `configurar-correo-soporte`).
 */

import type { Idioma } from '@/types'

/** Rol de un turno del historial que el cliente conserva localmente. */
export type RolTurno = 'usuario' | 'asistente'

export interface TurnoChat {
  rol: RolTurno
  texto: string
}

/** Veredicto del pipeline: espeja `VeredictoChat` del backend. */
export type VeredictoChat = 'respondida' | 'sin_resultados' | 'fuera_de_scope' | 'escalar'

/** Motivo del escalamiento cuando `veredicto === 'escalar'`. */
export type RazonEscalamientoChat =
  | 'solicitud_usuaria'
  | 'sin_resultados'
  | 'tope_turnos'
  | 'error_proveedor'

export interface FuenteChat {
  n: number
  tipo: 'articulo' | 'documento'
  titulo: string
  /** Vacío para documentos; el `slug` del artículo cuando `tipo === 'articulo'`. */
  slug: string
}

/**
 * Salida del BFF, con el veredicto como discriminante.
 *
 * `fuentes` solo tiene valores con `respondida`. `razon` y `conversacion` solo
 * viajan con `escalar`. `fuera_de_scope` no lleva ni fuentes ni conversación.
 * La estructura es intencionalmente ancha (un solo tipo con campos opcionales)
 * en vez de una unión discriminada estricta, porque el backend siempre serializa
 * los mismos campos (algunos vacíos) y así el consumidor puede leer `chat_id`
 * y `mensaje` sin ramificar por veredicto.
 */
export interface RespuestaChat {
  veredicto: VeredictoChat
  mensaje: string
  chat_id: string
  fuentes: FuenteChat[]
  razon: RazonEscalamientoChat | null
  conversacion: TurnoChat[]
}

export interface OpcionesConsulta {
  consulta: string
  historial: TurnoChat[]
  chatId?: string | null
  solicitarSoporte?: boolean
  /** Sustituible en tests; en producción se resuelve al `fetch` global del navegador. */
  fetchImpl?: typeof fetch
}

/**
 * Error de red o de contrato del BFF del chat. El widget lo captura y muestra un
 * mensaje neutro al usuario (no propaga el detalle técnico a la interfaz).
 */
export class ErrorChat extends Error {
  readonly estado?: number
  constructor(mensaje: string, estado?: number) {
    super(mensaje)
    this.name = 'ErrorChat'
    this.estado = estado
  }
}

/**
 * Llama al BFF del chat y devuelve la respuesta ya tipada.
 *
 * El cliente **no** adjunta `portal_id`: es el servidor quien lo resuelve del host
 * (cualquier `portal_id` en el cuerpo lo ignora el backend). Tampoco fuerza el
 * `content-type`: el BFF lo copia tal cual.
 */
export async function consultarChat(
  idioma: Idioma,
  { consulta, historial, chatId, solicitarSoporte, fetchImpl }: OpcionesConsulta,
): Promise<RespuestaChat> {
  const f = fetchImpl ?? fetch
  const cuerpo: Record<string, unknown> = { consulta, historial }
  if (chatId) cuerpo.chat_id = chatId
  if (solicitarSoporte) cuerpo.solicitar_soporte = true

  const resp = await f(`/api/${idioma}/chat/consultar`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(cuerpo),
  })

  if (!resp.ok) {
    // El texto crudo del backend puede ser una lista de errores de Pydantic;
    // el widget no lo muestra, pero se conserva en el mensaje para diagnóstico.
    const texto = await resp.text().catch(() => '')
    throw new ErrorChat(texto || `Error ${resp.status}`, resp.status)
  }

  return (await resp.json()) as RespuestaChat
}

/**
 * Serializa una conversación a texto plano legible.
 *
 * Formato: cada turno en su propia línea, precedido por la etiqueta bilingüe
 * del rol (`Usuario:` / `Assistente:`). Pensado para adjuntarse al `mailto:`
 * del botón "Contactar soporte" y, más adelante, al cuerpo del formulario de
 * `configurar-correo-soporte`. Sin HTML: se copia y pega tal cual.
 *
 * `\n` como separador de turnos (no `\r\n`): la mayoría de clientes de correo
 * lo interpretan bien en el `body` del `mailto:` y evita duplicar bytes.
 */
export function serializarConversacion(conversacion: TurnoChat[], idioma: Idioma): string {
  const etiquetas: Record<Idioma, Record<RolTurno, string>> = {
    es: { usuario: 'Usuario', asistente: 'Asistente' },
    pt: { usuario: 'Usuário', asistente: 'Assistente' },
  }
  return conversacion.map(t => `${etiquetas[idioma][t.rol]}: ${t.texto}`).join('\n')
}
