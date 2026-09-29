/**
 * `fetch` del cliente hacia el BFF de Next. Sustituye a `authFetch`: ya no hay
 * token en `localStorage` ni cabecera `Authorization` a mano. La sesión viaja en
 * la cookie `httpOnly` que el navegador adjunta sola en las peticiones
 * al mismo origen; el BFF la lee en servidor, renueva si hace falta y reenvía el
 * `Bearer` al backend. Devuelve la `Response` sin interpretar: cada pantalla
 * reacciona a su código (401 → login, 409 → conflicto, etc.).
 */
export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(input, { ...init, headers, credentials: 'same-origin' })
}
