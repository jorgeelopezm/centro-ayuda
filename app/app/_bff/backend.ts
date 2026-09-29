/**
 * Llamadas del BFF al backend FastAPI. Solo se ejecutan en el servidor de Next
 * (Route Handlers): el navegador nunca ve estas URLs ni los tokens que viajan.
 *
 * Cada llamada reenvía el host del portal (`X-Forwarded-Host`) para que el backend
 * resuelva el portal del host: sin él, el login o el refresh caerían en «portal no
 * encontrado». El host se toma del `Host` entrante de confianza, no del cliente.
 */

import { CABECERA_PORTAL } from '@/bff/portal'

// `127.0.0.1` y no `localhost`: el fetch de Node resuelve `localhost` a IPv6
// primero y uvicorn escucha en IPv4 (ver `src/data/servidor.ts`).
export const BACKEND = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'

/** Cabeceras JSON + reenvío del host del portal (si se conoce). */
function cabeceras(host: string): Record<string, string> {
  const base: Record<string, string> = { 'content-type': 'application/json' }
  if (host) base[CABECERA_PORTAL] = host
  return base
}

export function backendLogin(email: string, password: string, host: string): Promise<Response> {
  return fetch(`${BACKEND}/api/auth/login`, {
    method: 'POST',
    headers: cabeceras(host),
    body: JSON.stringify({ email, password }),
    cache: 'no-store',
  })
}

export function backendRefresh(refreshToken: string, host: string): Promise<Response> {
  return fetch(`${BACKEND}/api/auth/refresh`, {
    method: 'POST',
    headers: cabeceras(host),
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: 'no-store',
  })
}

export function backendLogout(refreshToken: string, host: string): Promise<Response> {
  return fetch(`${BACKEND}/api/auth/logout`, {
    method: 'POST',
    headers: cabeceras(host),
    body: JSON.stringify({ refresh_token: refreshToken }),
    cache: 'no-store',
  })
}
