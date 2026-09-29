// Configuración de Next.js (App Router). Convive con la SPA de Vite durante la
// migración `migrar-frontend-nextjs`: Next enruta desde `app/` (raíz del
// frontend) e ignora `src/` para el enrutado, así que `src/pages/*` de la SPA
// no se interpreta como Pages Router.

/**
 * Cabeceras de seguridad estáticas (iguales en cada respuesta), aplicadas a
 * todas las rutas para cubrir también los recursos. La CSP no está aquí: lleva
 * un nonce por petición y se emite desde `middleware.ts`.
 *
 * - `X-Content-Type-Options: nosniff` — el navegador no adivina tipos MIME.
 * - `Referrer-Policy` — no filtra la ruta completa a orígenes ajenos.
 * - `X-Frame-Options: DENY` — respaldo heredado de `frame-ancestors 'none'`.
 * - `Permissions-Policy` — desactiva APIs de dispositivo que la app no usa.
 * - `Strict-Transport-Security` — deshabilitada por ahora: NODE_ENV === 'production'
 *   no implica que el host sirva HTTPS. En plat.lupaterra.com el proceso corre en
 *   modo producción pero Caddy todavía sirve el hostname solo por HTTP (TLS por
 *   proyecto no está wireado hasta antel-infra 6.1); con el header activo, un
 *   navegador que lo cachea fuerza HTTPS en toda petición futura al host —
 *   incluidos los chunks de `_next/static/*`— y el sitio deja de cargar. Volver
 *   a activarla cuando el TLS por host esté garantizado en el entorno de destino.
 */
const CABECERAS_SEGURIDAD = [
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()' },
]

/** @type {import('next').NextConfig} */
const nextConfig = {
  async headers() {
    return [{ source: '/:path*', headers: CABECERAS_SEGURIDAD }]
  },
  // Sin rewrites: todo `/api/*` lo atienden Route Handlers que reenvían al backend el
  // host del portal (`X-Forwarded-Host`), imprescindible en multi-tenant para resolver el
  // portal por host. El contenido público por idioma lo sirve `app/api/[idioma]/contenido`
  // (cliente) o `src/data/servidor.ts` (SSR); la marca, `app/api/marca/*`; la sesión, el
  // BFF (`/api/admin/*`, `/api/auth/*`). Un rewrite no puede fijar esa cabecera.
}

export default nextConfig
