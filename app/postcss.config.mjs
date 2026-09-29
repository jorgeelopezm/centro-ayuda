// Tailwind v4 para Next.js vía PostCSS. La SPA de Vite usa `@tailwindcss/vite`
// y NO este archivo: `vite.config.ts` fija `css.postcss` en línea para no
// autocargar esta configuración y evitar procesar Tailwind dos veces.
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}
