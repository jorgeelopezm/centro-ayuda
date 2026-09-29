import { createInstance, type TFunction } from 'i18next'
import type { Idioma } from '@/types'
import { recursos } from './recursos'

/**
 * Traductor isomórfico para la app Next: funciona igual en Server Components y
 * en Client Components. A diferencia de react-i18next, no depende de un idioma
 * "activo" mutable: `getFixedT(idioma)` es una función pura, así que no hay
 * fugas entre peticiones concurrentes en el servidor ni desajustes de
 * hidratación. El idioma llega siempre por el segmento de ruta.
 *
 * La instancia se inicializa de forma síncrona (`initImmediate: false`) con los
 * recursos ya en memoria, de modo que `traducir` está listo desde el import.
 */
const instancia = createInstance()

void instancia.init({
  resources: recursos,
  fallbackLng: 'es',
  defaultNS: 'ui',
  interpolation: { escapeValue: false },
  returnObjects: true,
  initImmediate: false,
})

export function traducir(idioma: Idioma): TFunction {
  return instancia.getFixedT(idioma, 'ui')
}
