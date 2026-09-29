/**
 * Resolución de la plantilla del centro de ayuda a partir del valor publicado por la
 * API. Es lógica pura —sin red ni componentes— para poder probarla y para concentrar en
 * un solo sitio el respaldo: la API valida y normaliza al escribir y al leer, pero el
 * cliente no depende de que el valor llegue reconocible (un despliegue antiguo, un valor
 * manipulado), y nunca se queda sin plantilla que renderizar.
 */

import type { Idioma, PlantillaCentroAyuda } from '@/types'

/** Plantillas admitidas, en el orden en que se ofrecen en el panel. */
export const PLANTILLAS: readonly PlantillaCentroAyuda[] = ['default', 'documentacion']

/** Plantilla que se renderiza cuando el valor falta o no se reconoce. */
export const PLANTILLA_POR_DEFECTO: PlantillaCentroAyuda = 'default'

/**
 * Plantilla a renderizar:
 * - valor admitido → él mismo;
 * - ausente (`undefined`/`null`) o desconocido → `'default'`.
 */
export function resolverPlantilla(valor: string | null | undefined): PlantillaCentroAyuda {
  return PLANTILLAS.includes(valor as PlantillaCentroAyuda)
    ? (valor as PlantillaCentroAyuda)
    : PLANTILLA_POR_DEFECTO
}

/**
 * ¿La ruta pertenece a la superficie de administración (panel interno o login)?
 *
 * La plantilla del centro de ayuda es presentación del sitio **público**: el panel interno
 * conserva su aspecto y sus pantallas con cualquiera de las dos plantillas (y el login, que
 * es su puerta de entrada), así que el armazón de documentación no se monta en estas rutas.
 * Función pura para poder probar la decisión —y su borde— sin renderizar nada.
 */
export function esRutaAdministracion(pathname: string, idioma: Idioma): boolean {
  const panel = `/${idioma}/panel`
  return pathname === panel || pathname.startsWith(`${panel}/`) || pathname === `/${idioma}/login`
}
