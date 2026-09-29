import type { Metrica, PreguntaSinResolver } from '@/types'

export const preguntasSinResolver: PreguntaSinResolver[] = [
  { pregunta: 'Como troco minha senha pelo aplicativo?', veces: 47, similitud: 0.92, fecha: '2026-07-15', estado: 'nueva' },
  { pregunta: 'Quanto tempo leva o reembolso após a devolução aprovada?', veces: 38, similitud: 0.76, fecha: '2026-07-18', estado: 'revision' },
  { pregunta: 'Posso ter duas contas com o mesmo e-mail?', veces: 29, similitud: 0.88, fecha: '2026-07-20', estado: 'cubierta' },
  { pregunta: 'Como exporto meu histórico de pedidos em PDF?', veces: 24, similitud: 0.41, fecha: '2026-07-21', estado: 'nueva' },
  { pregunta: 'Dá para mudar o endereço de entrega depois de confirmar?', veces: 19, similitud: 0.65, fecha: '2026-07-22', estado: 'revision' },
  { pregunta: 'O que acontece se meu pacote chegar danificado?', veces: 15, similitud: 0.53, fecha: '2026-07-24', estado: 'nueva' },
]

export const metricas: Metrica[] = [
  { clave: 'sinResolver', valor: '34' },
  { clave: 'conCita', valor: '72 %' },
  { clave: 'creados', valor: '18' },
]
