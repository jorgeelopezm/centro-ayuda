# Centro de Ayuda — Frontend (Next.js)

Aplicación web del Centro de Ayuda: **Next.js 16 (App Router) + React 19 + TypeScript**, bilingüe
(español y portugués) y accesible (WCAG 2.2 AA). Migrada desde el prototipo SPA (React + Vite +
react-router) en el cambio OpenSpec `migrar-frontend-nextjs`.

## Arquitectura en dos frases

- **Contenido público en servidor** (Server Components): inicio y artículo llegan en el HTML inicial; solo
  son islas de cliente los componentes con estado.
- **Sesión de administrador en cookies `httpOnly` (patrón BFF)**: el token JWT nunca llega al navegador; lo
  custodian los Route Handlers de `app/api/*`, apoyados en `app/_bff/` (llamadas server-only al backend),
  que reenvían al backend con `Authorization: Bearer` y renuevan con un refresh token opaco y rotatorio. Las
  guardias del panel se resuelven en servidor.
- **Multi-tenant por portal**: el `portal_id` se resuelve del host de la petición (`proxy.ts` + `src/bff/portal.ts`),
  nunca del cliente; cada portal tiene su propia marca (logo, acento, nombre de empresa).
- **Plantilla del centro de ayuda por portal** (cambio OpenSpec `plantillas-centro-ayuda`): cada portal elige
  la estructura visual de su sitio público. `default` es el diseño actual (banner con buscador, rejilla de
  categorías y populares) y `documentacion` el armazón de documentación (cabecera con buscador, barra lateral
  persistente de la base de conocimiento, columna de contenido y pie). El valor viaja en
  `GET /api/{idioma}/contenido` (`plantilla`) para que el HTML inicial salga ya con el armazón correcto, y el
  Administrador lo cambia con `PUT /api/admin/ajustes/plantilla` desde la pestaña Administración del panel. Un
  valor desconocido se resuelve a `default` (`src/plantillas/plantillas.ts`); el panel interno no cambia.

## Comandos

```bash
npm install        # una sola vez
npm run dev        # servidor de desarrollo en http://localhost:3000
npm run build      # comprueba tipos y compila (next build)
npm start          # sirve la compilación de producción (next start)
npm test           # tests con Vitest (una pasada)
npm run test:watch # tests en modo continuo
```

En desarrollo hacen falta los tres procesos: `docker compose up -d` (Postgres, en la raíz), `uvicorn` en
`api/` y `npm run dev` aquí. Sin rewrites: todo `/api/*` (contenido público, marca, auth y panel) lo
atienden Route Handlers de Next que reenvían al backend (`127.0.0.1:8000`) con el host del portal, necesario
para que el backend resuelva el tenant. El origen del backend se configura con `BACKEND_ORIGIN`.

## Estructura

```
app/[idioma]/       Rutas por idioma: inicio, artículo, login, panel (con usuarios, portales —SuperAdmin—
                    y documentos), error y 404
app/api/            Route Handlers del BFF: auth, proxy de /api/admin/* y /api/marca/* con la cookie, y
                    BFF Anonymous del contenido público y del chat (reenvían X-Forwarded-Host)
app/_bff/           Llamadas server-only al backend (login/refresh con reenvío de host) y sesionServidor()
                    para las guardias del panel; usado solo por los Route Handlers, nunca por el cliente
app/_componentes/   Componentes de servidor y cliente de las pantallas (incl. ChatWidget, GestionPortales,
                    panel/PanelSugerencias, plantillas/documentacion con el armazón de documentación)
proxy.ts            Guardia del panel en el borde + resolución de portal por host + CSP con nonce
src/components/     Componentes reutilizados (Tabs, Modal, formularios, chips, iconos, acordeón)
src/bff/            Cookies httpOnly, cliente del panel (apiFetch) y resolución de portal por host (portal.ts)
src/seguridad/      Construcción de la Content-Security-Policy
src/data/{es,pt}/   Contenido tipado por idioma (alimenta el seed y los tests de paridad, por portal)
src/i18n/           i18next: traductor isomórfico (getFixedT), traducciones y rutas
src/plantillas/     Resolución de la plantilla activa del portal (valor desconocido → default)
src/types.ts        Contrato de datos compartido con la API
```

## Tests

Vitest en entorno `node`, **solo lógica pura** (`src/**/*.test.ts`): `src/data/`, `src/i18n/`,
`src/types.ts`, `src/auth/nivel.ts`, `src/bff/cookies.ts`, `src/seguridad/csp.ts`, `src/panel/panelPestanas.ts`
y `src/plantillas/plantillas.ts`. Los componentes y los Route Handlers no se prueban con Vitest.

## Seguridad

CSP estricta con nonce por petición (`src/seguridad/csp.ts`, emitida desde `proxy.ts`; `script-src` con
nonce + `strict-dynamic`, sin `unsafe-inline`) y cabeceras estáticas en `next.config.mjs` (HSTS —solo en
producción—, `nosniff`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`). Las cookies de sesión
son `httpOnly`, `SameSite=Lax` y `Secure` en producción.
