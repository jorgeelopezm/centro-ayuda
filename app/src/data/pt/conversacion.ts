import type { MensajeChat } from '@/types'

export const conversacion: MensajeChat[] = [
  {
    autor: 'asistente',
    clase: 'saludo',
    texto: 'Olá, sou o assistente da [EMPRESA]. Posso ajudar com perguntas sobre sua conta, pedidos, devoluções e mais. Como posso ajudar?',
  },
  {
    autor: 'usuario',
    texto: 'Como posso iniciar uma devolução?',
  },
  {
    autor: 'asistente',
    clase: 'citado',
    fragmentos: [
      { tipo: 'texto', texto: 'Para iniciar uma devolução você tem um prazo de ' },
      { tipo: 'texto', texto: '30 dias corridos', enfasis: 'fuerte' },
      { tipo: 'texto', texto: ' a partir da data de recebimento.' },
      { tipo: 'cita', n: 1 },
      { tipo: 'texto', texto: ' O produto deve estar no estado original, sem uso e com a embalagem intacta.' },
      { tipo: 'cita', n: 2 },
      { tipo: 'texto', texto: ' Vá em ' },
      { tipo: 'texto', texto: 'Minha conta → Pedidos → Solicitar devolução', enfasis: 'cursiva' },
      { tipo: 'texto', texto: ' e siga os passos indicados.' },
    ],
    citas: [
      { n: 1, titulo: 'Prazos de devolução: tudo o que você precisa saber', articuloId: 'plazos-devolucion' },
      { n: 2, titulo: 'Como iniciar uma devolução passo a passo', articuloId: 'iniciar-devolucion' },
    ],
  },
  {
    autor: 'usuario',
    texto: 'Posso devolver software baixado digitalmente?',
  },
  {
    autor: 'asistente',
    clase: 'sin-resultado',
    aviso: 'Não encontrado na base de conhecimento',
    texto: 'Não encontrei informações sobre devolução de produtos digitais na nossa base de conhecimento. Um atendente humano poderá ajudar melhor.',
  },
]
