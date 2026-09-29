/**
 * Reenvío del host del portal desde Next hacia el backend.
 *
 * El backend resuelve el portal a partir del host de la petición (nunca de un parámetro
 * del cliente). Como todas las llamadas de Next van al origen interno del backend
 * (`127.0.0.1:8000`), el `Host` que undici deriva de esa URL no identificaría ningún
 * portal. Por eso Next reenvía el host del navegador en `X-Forwarded-Host`, y el backend
 * lo prefiere sobre `Host` (ver `app/deps.py::_host_de_confianza`).
 *
 * Se lee siempre del `Host` entrante de confianza, no de un `X-Forwarded-Host` que
 * pudiera mandar el cliente: así el portal lo fija el host real, no un valor suplantable.
 */
export const CABECERA_PORTAL = 'x-forwarded-host'

// Basta con `.get`: así acepta tanto `Headers` (route handlers, `NextRequest`) como
// `ReadonlyHeaders` (`next/headers`), que no es asignable a `Headers` por ser inmutable.
type ConGet = Pick<Headers, 'get'>

/** Host del navegador (sin puerto lo normaliza el backend) para reenviarlo al backend. */
export function hostEntrante(headers: ConGet): string {
  return headers.get('host') ?? ''
}

/** Cabeceras de reenvío del portal, listas para fusionar en un `fetch` al backend. */
export function cabecerasPortal(headers: ConGet): Record<string, string> {
  const host = hostEntrante(headers)
  return host ? { [CABECERA_PORTAL]: host } : {}
}
