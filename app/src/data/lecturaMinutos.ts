/**
 * Cálculo de los minutos de lectura de un artículo por conteo de palabras.
 *
 * Determinista y sin IA: se cuenta el texto del contenido a un ritmo de
 * referencia de ~200 palabras por minuto. Es lógica pura (sin DOM ni red) y el
 * formulario la usa para mostrar el campo de solo lectura, recalculándolo a
 * medida que cambia el contenido.
 */

import type { TradDraft } from './articuloBorrador'

/** Ritmo de lectura de referencia (palabras por minuto). */
export const PALABRAS_POR_MINUTO = 200

/** Cuenta palabras separando por espacios; el texto vacío cuenta 0. */
export function contarPalabras(texto: string): number {
  const limpio = texto.trim()
  return limpio === '' ? 0 : limpio.split(/\s+/).length
}

/**
 * Minutos para un número de palabras: redondeo al minuto, con un mínimo de 1.
 * (400 palabras -> 2; menos de 200 -> 1.)
 */
export function minutosDePalabras(palabras: number): number {
  return Math.max(1, Math.round(palabras / PALABRAS_POR_MINUTO))
}

/** Junta en un solo texto todo el contenido legible de una traducción. */
export function textoDeTraduccion(t: TradDraft): string {
  const pasos = t.pasos.map(p => `${p.titulo} ${p.descripcion}`)
  const faq = t.faq.map(f => `${f.pregunta} ${f.respuesta}`)
  return [t.titulo, t.parrafos, t.nota, t.howToTitulo, ...pasos, ...faq].join(' ')
}

/** Minutos de lectura de una traducción concreta. */
export function minutosDeTraduccion(t: TradDraft): number {
  return minutosDePalabras(contarPalabras(textoDeTraduccion(t)))
}

/**
 * Minutos de lectura del artículo: el mayor entre español y portugués, para que
 * traducir a un idioma más extenso no rebaje la estimación del otro.
 */
export function minutosDeArticulo(es: TradDraft, pt: TradDraft): number {
  return Math.max(minutosDeTraduccion(es), minutosDeTraduccion(pt))
}
