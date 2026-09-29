import es from './locales/es/ui.json'
import pt from './locales/pt/ui.json'

/**
 * Recursos de traducción de la interfaz, sin efectos secundarios. Lo consumen
 * tanto la configuración de react-i18next de la SPA (`config.ts`) como el
 * traductor isomórfico de la migración a Next (`traducir.ts`).
 */
export const recursos = {
  es: { ui: es },
  pt: { ui: pt },
}
