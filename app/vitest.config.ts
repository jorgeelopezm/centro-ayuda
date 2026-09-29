import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'

/**
 * Configuración propia de los tests, separada de `vite.config.ts` a propósito.
 *
 * No carga los plugins de React ni de Tailwind: solo se prueba lógica pura en
 * `.ts`, sin JSX ni CSS. Además, Vitest trae anidada su propia copia de Vite
 * (basada en rollup) y el proyecto usa Vite 8 (rolldown); mezclar ambos en el
 * mismo archivo hace que los tipos de `Plugin` dejen de encajar.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    // Sin DOM: lo que necesita `fetch` lo sustituye por dobles en el propio test.
    environment: 'node',
    // Solo lógica pura de `src/` (data, i18n, types, auth/nivel, bff/cookies,
    // seguridad/csp, panel/panelPestanas). El árbol de rutas de Next (`app/`)
    // queda fuera: sus componentes y Route Handlers no se prueban con Vitest.
    include: ['src/**/*.test.ts'],
    exclude: ['node_modules', 'dist', '.next', 'app/**'],
  },
})
