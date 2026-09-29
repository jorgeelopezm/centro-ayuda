/**
 * Contrato de las cookies de sesión del BFF. Módulo puro (sin dependencias de
 * Next) para poder probar los atributos de seguridad con Vitest.
 *
 * El access token (JWT corto) y el refresh token (opaco) viven en cookies
 * **`httpOnly`**: el JavaScript del navegador no puede leerlos, así que un XSS
 * no puede exfiltrar la sesión. `SameSite=Lax` corta el envío en peticiones de
 * terceros. `Secure` solo en producción: en `http://localhost` de desarrollo una
 * cookie `Secure` no se almacenaría.
 *
 * **Alcance por host (multi-tenant).** Las cookies NO llevan atributo `Domain`: son
 * *host-only*, atadas al host exacto que las emitió (`cliente-a.tuapp.com`). Así la
 * sesión de un portal nunca viaja al host de otro. Poner `Domain=.tuapp.com` la
 * compartiría entre todos los subdominios (fuga de sesión entre portales), justo lo
 * contrario de lo que buscamos: por eso la omisión de `domain` es deliberada, no un
 * olvido. `SameSite` no basta para aislar —`cliente-a` y `cliente-b` son *same-site*
 * bajo el mismo dominio registrable—; el aislamiento lo da el alcance host-only.
 */

export const COOKIE_ACCESS = 'ca_sesion'
export const COOKIE_REFRESH = 'ca_refresh'

/** Vida de las cookies. El access acompaña al JWT (60 min); el refresh, 14 días. */
export const MAX_AGE_ACCESS = 60 * 60
export const MAX_AGE_REFRESH = 14 * 24 * 60 * 60

export interface OpcionesCookie {
  httpOnly: true
  secure: boolean
  sameSite: 'lax'
  path: '/'
  maxAge: number
}

export function opcionesCookie(maxAgeSegundos: number): OpcionesCookie {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: maxAgeSegundos,
  }
}

/** Opciones para borrar una cookie (expiración inmediata), conservando `path`. */
export function opcionesBorrado(): OpcionesCookie {
  return opcionesCookie(0)
}
