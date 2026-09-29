/**
 * Normalización de identificadores y slugs, compartida con el backend
 * (`api/app/texto.py::normalizar_slug`): la misma regla en cliente y servidor.
 *
 * El cliente la usa para adelantar la vista (autogenerar id y slug mientras el
 * administrador escribe el título); el servidor la reaplica como autoridad. Es
 * lógica pura: se prueba sin DOM ni red.
 */

// Rango Unicode de los diacríticos combinantes (U+0300–U+036F), lo que deja NFKD
// tras separar un acento de su letra. Se escribe con escapes para no depender de
// cómo guarde el editor los caracteres combinantes.
const DIACRITICOS = /[̀-ͯ]/g

/**
 * Minúsculas, sin acentos, con espacios y signos convertidos en guiones y sin
 * guiones repetidos ni en los extremos.
 *
 * Ej.: "Cómo cambiar tu contraseña" -> "como-cambiar-tu-contrasena".
 */
export function normalizarSlug(texto: string): string {
  return texto
    .normalize('NFKD') // descompone acentos: "á" -> "a" + diacrítico
    .replace(DIACRITICOS, '') // descarta los diacríticos combinantes
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-') // cualquier no alfanumérico ASCII pasa a guion
    .replace(/^-+|-+$/g, '') // sin guiones al principio ni al final
}

/**
 * Identificador de un artículo: se deriva del título en español, la clave
 * estable entre idiomas. Es `normalizarSlug`, con nombre propio para dejar claro
 * de qué título nace.
 */
export function derivarId(tituloEspanol: string): string {
  return normalizarSlug(tituloEspanol)
}

/** Slug de un idioma: se deriva del título de ese mismo idioma. */
export function derivarSlug(tituloDelIdioma: string): string {
  return normalizarSlug(tituloDelIdioma)
}
