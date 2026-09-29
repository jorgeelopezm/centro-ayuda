import type { Idioma } from '@/types'

/**
 * Constructores de direcciones. Cada dirección lleva el idioma en el primer
 * segmento, de modo que un artículo citado por el asistente resuelve siempre
 * al mismo contenido y en el mismo idioma.
 */
export const rutas = {
  inicio: (idioma: Idioma) => `/${idioma}`,
  articulo: (idioma: Idioma, slug: string) => `/${idioma}/articulo/${slug}`,
  panel: (idioma: Idioma) => `/${idioma}/panel`,
  usuarios: (idioma: Idioma) => `/${idioma}/panel/usuarios`,
  portales: (idioma: Idioma) => `/${idioma}/panel/portales`,
  documentos: (idioma: Idioma) => `/${idioma}/panel/documentos`,
  login: (idioma: Idioma) => `/${idioma}/login`,
  /**
   * Entrada al panel interno sin enlace en la cabecera pública: redirige a `panel`, cuya
   * guardia muestra el login si no hay sesión. El segmento va traducido por idioma.
   */
  panelInterno: (idioma: Idioma) => `/${idioma}/${idioma === 'pt' ? 'painel-interno' : 'panel-interno'}`,
}
