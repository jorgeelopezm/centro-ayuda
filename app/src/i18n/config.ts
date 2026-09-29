import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import type { Idioma } from '@/types'
import { recursos } from './recursos'

export { recursos }

void i18n.use(initReactI18next).init({
  resources: recursos,
  lng: 'es',
  fallbackLng: 'es',
  defaultNS: 'ui',
  interpolation: {
    // React ya escapa el contenido interpolado.
    escapeValue: false,
  },
  returnObjects: true,
})

/**
 * Idioma preferido del navegador, usado **solo** para decidir la redirección
 * desde la raíz. Una vez dentro, manda el segmento de la dirección.
 */
export function detectarIdioma(): Idioma {
  const preferidos = navigator.languages ?? [navigator.language]
  for (const etiqueta of preferidos) {
    if (etiqueta.toLowerCase().startsWith('pt')) return 'pt'
    if (etiqueta.toLowerCase().startsWith('es')) return 'es'
  }
  return 'es'
}

export default i18n
