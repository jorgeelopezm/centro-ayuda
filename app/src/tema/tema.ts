/**
 * Preferencia de tema (modo noche) de la plantilla de documentación. Lógica pura —sin
 * DOM ni cookies reales— para probarla y para que servidor y cliente decidan igual.
 *
 * La preferencia viaja en una cookie **no** `httpOnly` (`tema`): es una preferencia de
 * presentación, no un secreto, y el botón la escribe desde el cliente. El layout la lee
 * en servidor para que el HTML inicial ya salga con el tema correcto (sin parpadeo).
 * Sin cookie, `sistema`: el CSS sigue `prefers-color-scheme` sin JavaScript.
 */

export type Tema = 'claro' | 'oscuro' | 'sistema'

export const COOKIE_TEMA = 'tema'

/** Un año: la preferencia es duradera, como el idioma. */
const MAX_AGE_SEG = 60 * 60 * 24 * 365

/** Valor de la cookie → tema. Ausente o desconocido (manipulado) → `sistema`. */
export function resolverTema(valor: string | null | undefined): Tema {
  return valor === 'claro' || valor === 'oscuro' ? valor : 'sistema'
}

/**
 * Tema que fija el botón: el contrario del que se ve ahora. Con `sistema` lo que se ve
 * depende de la preferencia del sistema, así que la decide quien llama (`matchMedia`).
 */
export function alternarTema(oscuroVisible: boolean): Exclude<Tema, 'sistema'> {
  return oscuroVisible ? 'claro' : 'oscuro'
}

/** ¿Se ve oscuro? `sistema` delega en la preferencia del sistema. */
export function esOscuro(tema: Tema, sistemaOscuro: boolean): boolean {
  return tema === 'oscuro' || (tema === 'sistema' && sistemaOscuro)
}

/** Cadena para `document.cookie`: toda la web del host, `SameSite=Lax`. */
export function cookieTema(tema: Exclude<Tema, 'sistema'>, seguro: boolean): string {
  return `${COOKIE_TEMA}=${tema}; Path=/; Max-Age=${MAX_AGE_SEG}; SameSite=Lax${seguro ? '; Secure' : ''}`
}
