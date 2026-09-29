/**
 * Formateo de las fechas ISO (AAAA-MM-DD) del contenido.
 *
 * El `T00:00:00` no es adorno: sin él, `new Date('2026-07-25')` se interpreta
 * como medianoche UTC y en husos al oeste la fecha mostrada retrocede un día.
 * Con la hora explícita, el valor se lee como medianoche local y la fecha
 * visible coincide siempre con el atributo `datetime` del `<time>`.
 */
export function fechaLegible(iso: string, idioma: string, opciones?: Intl.DateTimeFormatOptions): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(idioma, opciones)
}

/** Día, mes en palabra y año: el formato de la cabecera del artículo. */
export const FECHA_LARGA: Intl.DateTimeFormatOptions = {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
}
