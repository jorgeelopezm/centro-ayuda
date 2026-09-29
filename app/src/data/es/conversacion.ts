import type { MensajeChat } from '@/types'

/**
 * Conversación fija del prototipo. No hay generación de respuestas: el chat es
 * interfaz sobre datos, y las citas apuntan a artículos que existen de verdad.
 */
export const conversacion: MensajeChat[] = [
  {
    autor: 'asistente',
    clase: 'saludo',
    texto: 'Hola, soy el asistente de [EMPRESA]. Puedo ayudarte con preguntas sobre tu cuenta, pedidos, devoluciones y más. ¿En qué puedo ayudarte?',
  },
  {
    autor: 'usuario',
    texto: '¿Cómo puedo iniciar una devolución?',
  },
  {
    autor: 'asistente',
    clase: 'citado',
    fragmentos: [
      { tipo: 'texto', texto: 'Para iniciar una devolución tienes un plazo de ' },
      { tipo: 'texto', texto: '30 días naturales', enfasis: 'fuerte' },
      { tipo: 'texto', texto: ' desde la fecha de recepción.' },
      { tipo: 'cita', n: 1 },
      { tipo: 'texto', texto: ' El producto debe estar en su estado original, sin usar y con el embalaje intacto.' },
      { tipo: 'cita', n: 2 },
      { tipo: 'texto', texto: ' Ve a ' },
      { tipo: 'texto', texto: 'Mi cuenta → Pedidos → Solicitar devolución', enfasis: 'cursiva' },
      { tipo: 'texto', texto: ' y sigue los pasos indicados.' },
    ],
    citas: [
      { n: 1, titulo: 'Plazos de devolución: todo lo que necesitas saber', articuloId: 'plazos-devolucion' },
      { n: 2, titulo: 'Cómo iniciar una devolución paso a paso', articuloId: 'iniciar-devolucion' },
    ],
  },
  {
    autor: 'usuario',
    texto: '¿Puedo devolver software descargado digitalmente?',
  },
  {
    autor: 'asistente',
    clase: 'sin-resultado',
    aviso: 'No encontrado en la base de conocimiento',
    texto: 'No encontré información sobre devoluciones de productos digitales en nuestra base de conocimiento. Un agente humano podrá ayudarte mejor.',
  },
]
