import { describe, expect, it } from 'vitest'
import { serializarConversacion, type TurnoChat } from './chat'

/**
 * `serializarConversacion` es el puente entre el chat y el cuerpo del `mailto:`
 * (y, más adelante, el formulario de soporte de `configurar-correo-soporte`).
 * Tres propiedades importan: paridad de etiquetas es/pt, orden preservado y
 * ausencia de trailing newlines (que algunos clientes de correo colapsan).
 */
describe('serializarConversacion', () => {
  const conversacion: TurnoChat[] = [
    { rol: 'usuario', texto: '¿Cómo cambio mi correo?' },
    { rol: 'asistente', texto: 'No encontré información en este portal.' },
    { rol: 'usuario', texto: 'Necesito hablar con soporte.' },
  ]

  it('etiqueta cada turno en español y respeta el orden', () => {
    const salida = serializarConversacion(conversacion, 'es')
    expect(salida).toBe(
      [
        'Usuario: ¿Cómo cambio mi correo?',
        'Asistente: No encontré información en este portal.',
        'Usuario: Necesito hablar con soporte.',
      ].join('\n'),
    )
  })

  it('etiqueta cada turno en portugués con las traducciones correctas', () => {
    const salida = serializarConversacion(
      [
        { rol: 'usuario', texto: 'Como troco meu e-mail?' },
        { rol: 'asistente', texto: 'Não encontrei informação neste portal.' },
      ],
      'pt',
    )
    // "Usuário" con tilde, "Assistente" con doble s.
    expect(salida).toBe(
      ['Usuário: Como troco meu e-mail?', 'Assistente: Não encontrei informação neste portal.'].join('\n'),
    )
  })

  it('devuelve cadena vacía cuando la conversación está vacía', () => {
    expect(serializarConversacion([], 'es')).toBe('')
    expect(serializarConversacion([], 'pt')).toBe('')
  })

  it('no añade newline final (importa para el body del mailto)', () => {
    const salida = serializarConversacion(conversacion, 'es')
    expect(salida.endsWith('\n')).toBe(false)
  })

  it('preserva saltos de línea y caracteres especiales dentro del texto', () => {
    const salida = serializarConversacion(
      [{ rol: 'usuario', texto: 'línea 1\nlínea 2  con acentos á é í ó ú ñ' }],
      'es',
    )
    expect(salida).toBe('Usuario: línea 1\nlínea 2  con acentos á é í ó ú ñ')
  })
})
