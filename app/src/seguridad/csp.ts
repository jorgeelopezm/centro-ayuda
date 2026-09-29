// Construcción de la cabecera Content-Security-Policy con nonce por petición.
// Vive aparte del `middleware` (que solo la aplica) para poder probarla como
// lógica pura con Vitest, sin Edge runtime ni `NextRequest`.

const ES_PROD = process.env.NODE_ENV === 'production'

/**
 * Construye la cabecera `Content-Security-Policy` para una petición, insertando
 * el `nonce` que Next propaga a sus `<script>`.
 *
 * Decisiones:
 * - `script-src` con `'nonce-…'` + `'strict-dynamic'`: solo se ejecuta el script
 *   raíz de Next (que lleva el nonce) y lo que él cargue; se ignora `'self'` y
 *   cualquier host, así que no hay lista blanca de dominios que mantener. En
 *   desarrollo se añade `'unsafe-eval'` porque el refresco en caliente lo exige.
 * - `style-src 'unsafe-inline'`: Tailwind y varios componentes usan `style=""`
 *   en línea (p. ej. `var(--acento)`); el riesgo de CSS en línea es mucho menor
 *   que el de un script y evita reescribir la interfaz. No se permite en scripts.
 * - `connect-src 'self'`: las llamadas del cliente van al BFF, mismo origen. En
 *   desarrollo se añade `ws:` para el websocket de recarga en caliente.
 * - `frame-ancestors 'none'` + `object-src 'none'` + `base-uri 'self'`: nadie
 *   puede embeber la app, no hay plugins y no se puede reescribir la base de URLs.
 * - `upgrade-insecure-requests` solo en producción (en local se sirve por http).
 *
 * Multi-tenant (revisión task 9.1): esta política **ya cubre cada host de portal**
 * (subdominio `marca.tuapp.com` y dominios propios) sin lista blanca de hosts, porque
 * es host-relativa: `'self'`/`default-src`/`connect-src` se resuelven contra el host que
 * sirvió la página, así que las llamadas del cliente de un portal nunca alcanzan el
 * origen de otro. `frame-ancestors 'none'` deniega el enmarcado de todo portal (no se
 * necesita ni se quiere enmarcado cruzado). El aislamiento de sesión lo completan las
 * cookies host-only (`src/bff/cookies.ts`). No hay hosts que enumerar aquí: añadir un
 * portal no toca la CSP.
 */
export function construirCSP(nonce: string): string {
  const directivas: Record<string, string[]> = {
    'default-src': ["'self'"],
    'script-src': [
      "'self'",
      `'nonce-${nonce}'`,
      "'strict-dynamic'",
      ...(ES_PROD ? [] : ["'unsafe-eval'"]),
    ],
    'style-src': ["'self'", "'unsafe-inline'"],
    'img-src': ["'self'", 'data:', 'blob:'],
    'font-src': ["'self'"],
    'connect-src': ["'self'", ...(ES_PROD ? [] : ['ws:'])],
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    'frame-src': ["'none'"],
    'frame-ancestors': ["'none'"],
    'manifest-src': ["'self'"],
  }

  const partes = Object.entries(directivas).map(([clave, valores]) => `${clave} ${valores.join(' ')}`)
  if (ES_PROD) partes.push('upgrade-insecure-requests')
  return partes.join('; ')
}
