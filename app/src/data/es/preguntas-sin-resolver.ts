import type { Metrica, PreguntaSinResolver } from '@/types'

export const preguntasSinResolver: PreguntaSinResolver[] = [
  { pregunta: '¿Cómo cambio mi contraseña desde la app móvil?', veces: 47, similitud: 0.92, fecha: '2026-07-15', estado: 'nueva' },
  { pregunta: '¿Cuánto tarda el reembolso tras una devolución aprobada?', veces: 38, similitud: 0.76, fecha: '2026-07-18', estado: 'revision' },
  { pregunta: '¿Puedo tener dos cuentas con el mismo correo?', veces: 29, similitud: 0.88, fecha: '2026-07-20', estado: 'cubierta' },
  { pregunta: '¿Cómo exporto mi historial de pedidos en PDF?', veces: 24, similitud: 0.41, fecha: '2026-07-21', estado: 'nueva' },
  { pregunta: '¿Se puede cambiar la dirección de envío tras confirmar?', veces: 19, similitud: 0.65, fecha: '2026-07-22', estado: 'revision' },
  { pregunta: '¿Qué ocurre si mi paquete llega dañado?', veces: 15, similitud: 0.53, fecha: '2026-07-24', estado: 'nueva' },
]

export const metricas: Metrica[] = [
  { clave: 'sinResolver', valor: '34' },
  { clave: 'conCita', valor: '72 %' },
  { clave: 'creados', valor: '18' },
]
