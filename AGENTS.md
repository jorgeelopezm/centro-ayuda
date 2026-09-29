# AGENTS.md

Este archivo proporciona orientación a los **agentes de código** que trabajan en este repositorio (Cline,
Claude Code, Codex, Cursor, Copilot y cualquier otro que siga la convención `AGENTS.md`). Su contenido es
**el mismo que el de `CLAUDE.md`**, que se conserva para Claude Code: si se edita uno, hay que editar el
otro para que no diverjan.

---

Aplicación de **Centro de Ayuda**. El **frontend** vive en `app/` (las 4 pantallas,
bilingüe), migrado a **Next.js (App Router) con renderizado en servidor y sesión en cookie httpOnly**
(cambio OpenSpec `migrar-frontend-nextjs`), y el **backend** en `api/` (FastAPI) incluye el control de
acceso en cuatro niveles Anonymous / Editor / Administrador / SuperAdmin. La aplicación es **multi-tenant
por portal** (cambio OpenSpec `multi-tenant-portales`): una sola instalación y una sola base de datos
sirven a varios clientes, cada uno con su propia URL (subdominio, con dominios propios preparados en el
modelo); todos los datos se discriminan por `portal_id` y el portal se resuelve **del host de la petición
en el servidor**. Varias secciones de este documento se irán completando a medida que se construya.

## Stack

El frontend vive en `app/`:

- **Next.js 16 (App Router) + React 19 + TypeScript.** Enrutado por archivos con el idioma en el primer
  segmento (`app/app/[idioma]/…` → `/es/…`, `/pt/…`); `next dev`/`next build` como servidor y empaquetador.
- **Contenido público renderizado en servidor** (Server Components): inicio y artículo llegan en el HTML
  inicial; solo son islas de cliente los componentes con estado.
- **Sesión de administrador en cookies `httpOnly` (patrón BFF).** El token JWT nunca llega al navegador:
  lo custodian los Route Handlers de `app/app/api/*`, apoyados en `app/app/_bff/` (llamadas server-only al
  backend con reenvío de `X-Forwarded-Host` y el helper de sesión de servidor), que reenvían al backend con
  `Authorization: Bearer`. Un refresh token opaco y rotatorio renueva el acceso. Las guardias del panel se
  resuelven en servidor (`app/proxy.ts` en el borde + `sesionActual()` en las páginas).
- **Traducción isomórfica** con i18next (`src/i18n/traducir.ts`, `getFixedT`), sin idioma global mutable;
  funciona igual en Server y Client Components. react-i18next se conserva solo para los componentes
  reutilizados del panel (`PanelI18n` fija el idioma antes de renderizarlos).
- **Tailwind CSS v4** mediante `@tailwindcss/postcss`, sin archivo de configuración; el acento sigue
  expuesto como token `--acento`.
- El contenido lo sirve la API por idioma; las pantallas lo consumen por `src/data/` sin tocar su ARIA.

Se llegó aquí **migrando el prototipo SPA** (React + Vite + react-router, con el token en `localStorage`)
a Next.js: cambio OpenSpec `migrar-frontend-nextjs` (SSR del contenido público, sesión en cookie httpOnly
y guardias en servidor). El razonamiento del prototipo original, con las alternativas descartadas, está en
`openspec/changes/archive/2026-07-28-prototipo-centro-ayuda/design.md`.

### Backend (`api/`, integrado)

Backend originado en el cambio OpenSpec `backend-cms-autenticacion` (modelos, routers, auth, seed y tests),
ya integrado en `main` y ampliado desde entonces por los cambios listados abajo (multi-tenant, RAG, chat,
proveedores de IA, sugerencias). El razonamiento original con alternativas está en el `design.md` de ese
cambio; el de cada ampliación, en el `design.md` del cambio correspondiente (archivado tras su PR).

- **FastAPI + Python** (Pydantic + SQLAlchemy + Alembic). Se eligió Python por el RAG futuro; los esquemas
  Pydantic reproducen `src/types.ts` campo a campo. Sin rewrites de Next: todo `/api/*` lo atienden Route
  Handlers que reenvían al backend el host del portal (`X-Forwarded-Host`), imprescindible en multi-tenant
  para resolver el portal por host (un rewrite no puede fijar esa cabecera).
- **PostgreSQL + pgvector** como única base de datos (RAG-ready desde la primera migración), levantada con
  Docker Compose. Modelo bilingüe entidad estable + traducciones por idioma; `parrafos`/`how_to`/`faq` en
  JSONB; métricas del panel derivadas por consulta.
- **Autenticación de administrador:** correo + contraseña con hash **argon2** y sesión **JWT**. Protege
  `/api/admin/*` y restringe el Panel Interno (`/:idioma/panel`) a sesión válida.
- **Control de acceso en cuatro niveles jerárquicos:** Anonymous (sin sesión, solo centro de ayuda),
  Editor (panel + funciones de producto), Administrador (además gestión de usuarios y marca del portal) y
  SuperAdmin (dueño de la plataforma: gestiona portales y asigna su Administrador). La dependencia
  `requiere_nivel` aplica la autorización **en el servidor** (403 por nivel insuficiente), leyendo nivel y
  estado `activo` de la base en cada petición (no del JWT), para revocar acceso al instante. Enum de niveles
  `SUPERADMIN=4 > ADMINISTRADOR=3 > EDITOR=2 > ANONIMO=1` (backend `models.py`, frontend `src/auth/nivel.ts`).
- **Aislamiento multi-tenant por portal (server-side):** el `portal_id` se resuelve **del host** (nunca del
  cuerpo, la ruta ni una cabecera que fije el cliente) y toda lectura/escritura filtra por él;
  `requiere_nivel` exige, además del nivel, que el recurso pertenezca al portal del host. Acceder a un
  recurso de otro portal por id directo responde **404** (no revela existencia). Administrador y Editor
  quedan acotados a su propio portal; SuperAdmin es transversal a la plataforma.
- **Consumo desde el frontend** con **Server Components de Next**: el contenido público se carga en el
  servidor (`src/data/servidor.ts`) y el panel usa el BFF por cookie (`src/bff/apiFetch.ts`), sin tocar
  componentes ni su ARIA.
- **Marca por portal:** logo, color de acento (con las paradas del banner) y nombre de empresa dejan de ser
  globales y pasan a ser ajustes **por portal**; el SSR carga la marca del portal resuelto y sirve su favicon
  desde el propio host, sin fuga ni parpadeo entre portales.
- **Plantilla del centro de ayuda por portal** (cambio OpenSpec `plantillas-centro-ayuda`): la **estructura
  visual** del sitio público también es un ajuste del portal. La columna `plantilla` de `ajustes` admite
  `default` (el diseño actual) y `documentacion` (armazón de documentación: cabecera con buscador, barra
  lateral persistente de la base de conocimiento, columna de contenido y pie); `default` es el valor por
  defecto y un valor desconocido se normaliza a `default` al leer (`app/servicios.py`). Viaja en
  `GET /api/{idioma}/contenido` (`plantilla`) para que el HTML inicial salga ya con el armazón correcto, y el
  Administrador la guarda con `PUT /api/admin/ajustes/plantilla` (422 si el valor no está admitido) desde la
  tarjeta «Plantilla del centro de ayuda» de la pestaña Administración. La misma dirección y el mismo
  contenido sirven con las dos plantillas; no hay dependencias nuevas (la CSP sigue estricta) y el panel
  interno no cambia de aspecto.
- **Chat con RAG por portal** (cambio OpenSpec `chat-rag-portal`): endpoint público Anonymous
  `POST /api/{idioma}/chat/consultar` que responde SOLO con base en los artículos y documentos indexados
  del portal resuelto por host. Pipeline en `app/chat.py`: clasificador de scope (LLM con temperatura 0)
  → recuperación vectorial acotada al portal (`app/recuperador.py`, pgvector coseno con fallback SQLite
  para tests) → generación con JSON estricto y validación de citas contra fragmentos y `portal_id`. Sesión
  efímera en memoria (`app/sesiones_chat.py`) con TTL; escalamiento a soporte por umbral de
  `sin_resultados` o petición explícita (`solicitar_soporte: true`). **Configuración de IA por rol**
  (cambio OpenSpec `separar-proveedores-ia`): `ConfigIA` tiene tres campos independientes
  (`proveedor_chat`, `proveedor_traduccion`, `proveedor_embeddings`) y las claves viven en la tabla
  `config_ia_clave` (una fila por proveedor, cifrada con Fernet). Motores implementados hoy: chat
  con **DeepSeek**; traducción con **Anthropic** o **DeepSeek**; embeddings con **Voyage AI**
  (default) o cualquier proveedor OpenAI-compatible (p. ej. OpenAI). SuperAdmin configura cada rol
  por separado en el panel; los selectores se filtran contra `rolesSoportados` que expone el
  backend, y el `PUT` rechaza con 422 cualquier asignación de rol → proveedor sin motor real.
- **Observabilidad y salud de los proveedores de IA:** todo fallo de proveedor (`ErrorProveedor`)
  se registra con su mensaje real y un `codigo` de correlación corto que también viaja en el cuerpo
  de la respuesta; al cliente se le da un texto genérico (el mensaje del proveedor puede llevar
  datos de cuenta). Antes ese texto se descartaba en `main.py` y la causa era irrecuperable.
  `app/sugerencias.py` etiqueta la etapa (`redaccion` / `traduccion`) porque ambas levantan el mismo
  error y daban el mismo 502. **Cada llamada saliente tiene timeout explícito y dimensionado por
  tamaño de salida** (`servicios_ia.py`): `TIMEOUT_CHAT_SEG`=30 s para los 512 tokens del chat,
  `TIMEOUT_GENERACION_SEG`=120 s para los 2048 de un borrador de sugerencia —reutilizar el del chat
  hacía fallar la generación por timeout de forma sistemática— y `TIMEOUT_TRADUCCION_SEG`=90 s en
  ambos traductores (sin él regía el default de 600 s de los SDK). El BFF acota además su `fetch`
  y devuelve 504 en vez de dejar escapar la excepción. `GET /api/admin/config-ia/salud`
  (SuperAdmin, `app/salud_ia.py`) sondea cada rol bajo demanda y separa `credenciales` (clave
  revocada) de `saldo` (cuenta sin fondos), que producen el mismo 502 pero se arreglan distinto;
  con caché en proceso de 60 s y sin devolver nunca el texto crudo del proveedor.
- **Claves de JSON traducidas por el proveedor:** `deepseek-chat` traduce al portugués las
  *claves* del JSON de traducción (`pregunta`/`respuesta` → `pergunta`/`resposta`,
  `descripcion` → `descricao`, `pasos` → `passos`) pese a que el prompt de sistema las enumera
  como literales y `_ESQUELETO_CLAVES` se las da como ejemplo de forma. Insistir por prompt está
  agotado: `_canonizar_contenido` (`servicios_ia.py`) las revierte de forma determinista con el
  mapa `_ALIAS_CLAVES` **antes** de `_validar_estructura`. La reparación es deliberadamente
  estrecha —solo renombra si el alias es conocido, la clave se espera ahí y la canónica no está ya
  presente— así que **no relaja el guardarraíl**: una clave inventada sigue cortando con
  `ErrorProveedor`, y ahora el mensaje nombra las claves sobrantes y las que faltan.
- **Brevedad, supervisión y evals del chat** (cambio OpenSpec `chat-evals-brevedad-supervision`):
  el identificador público del chat pasa a llamarse `chat_id` (alias entrante `session_id` mientras
  dure la transición) y cada interacción queda persistida en la tabla `chat_interaccion`
  (`portal_id`, `chat_id`, `turno`, `veredicto`, `mensaje`, `citas`, `latencia_ms`, `proveedor`,
  `modelo`, ...). El prompt de sistema pide **brevedad** (respuesta directa en la primera frase,
  máx. 3 frases fuera de pasos, procedimientos en línea `paso 1 > paso 2 > paso 3` con máx. 4
  pasos), `MAX_TOKENS_CHAT` = 512 corta la deriva del modelo y un recorte suave por caracteres
  (`CHAT_LONGITUD_MAX_CHARS`, default 1400) acota la respuesta final SOLO cuando el veredicto es
  `respondida`. **Caché por proceso** (`app/cache_chat.py`) con LRU + TTL corto (10 min) sobre
  `sha256(portal_id | idioma | consulta_normalizada | config_ia_version | schema_recuperacion)`
  cachea solo `respondida` y revalida la existencia de cada recurso citado antes de servir; sin
  streaming (validación estricta de JSON y de citas exige la respuesta completa). **Supervisión
  desde el panel** en la pestaña "Chats" (nivel ≥ Editor, entre "Gestión de artículos" y
  "Categorías"): tres KPIs (chats totales, % con cita, escalados), tabla agrupada por `chat_id` con
  filtros por veredicto y por rango de fechas, y modal con el hilo por turnos. Endpoints
  `GET /api/admin/chats`, `/api/admin/chats/{chat_id}` y `/api/admin/chats/metricas` en
  `api/app/routers/admin_chats.py`. **Harness EDD** en `api/tests/eval/` (marker `eval`, opt-in):
  dataset `casos_{es,pt}.jsonl` (22 casos por idioma cubriendo los 4 veredictos + adversarios),
  proveedor doble determinista + embedder doble para el modo `ci` sin red y `--real` con
  `CHAT_EVAL_HABILITADO_REAL=1` para medir contra el proveedor real; métricas
  (`exactitud_veredicto`, `precision_citas`, `recall_citas`, `longitud_media`,
  `pasos_en_formato_correcto`, `latencia_media_ms`, `coste_total_usd_estimado`) comparadas contra
  `baseline.json` — el gate falla el test si alguna cae bajo su umbral con el margen configurado.
- **Sugerencias de artículo asistidas por IA** (cambio OpenSpec `sugerir-articulos-ia`): tres
  agregadores por portal (`app/sugerencias.py`) convierten en "candidatos" los chats escalados
  (`chat_interaccion` con `veredicto=escalar`), las preguntas sin resolver y los huecos de
  documentación RAG (fragmentos indexados sin artículo que los cubra). La persona editora dispara
  la generación **bajo demanda** (nunca en lote) desde el panel; el pipeline redacta el borrador en
  español con `proveedor_chat` y lo completa en portugués con `proveedor_traduccion` (bilingüe
  atómico, sin roles nuevos en `ConfigIA`), reutilizando los guardarraíles del chat (separación
  instrucción/dato con nonce, JSON estricto, citas cruzadas contra el `portal_id`). El borrador se
  persiste como `SugerenciaArticulo` en estado `pendiente` — **nunca** público ni indexado — hasta
  que la editora lo revisa en el modal de formulario de artículo existente: "Aceptar" crea el
  artículo real por el alta ya existente (re-indexa RAG) y "Descartar" lo archiva sin publicar
  nada. Endpoints en `api/app/routers/admin_sugerencias.py` (nivel ≥ Editor, filtrados por portal):
  `GET /api/admin/sugerencias/candidatos`, `POST /api/admin/sugerencias/generar` (idempotente por
  candidato pendiente), `GET /api/admin/sugerencias`, `GET/POST /api/admin/sugerencias/{id}` y
  `POST /api/admin/sugerencias/{id}/aceptar|descartar`. Pestaña "Sugerencias" en el panel interno,
  entre "Chats" y "Categorías".
- **Alcance:** API de contenido + CRUD de artículos + auth + control de acceso por niveles, gestión de
  usuarios (Administrador), marca por portal, resolución de portal por host, gestión de portales
  (SuperAdmin), ingesta RAG por portal, chat con RAG por portal, supervisión de chats y harness
  EDD, **sugerencias de artículo asistidas por IA** ahora.

## Convenciones

Lo establecido hasta ahora:

- **Idiomas de la aplicación: español y portugués.** Todo texto de interfaz y contenido debe contemplar
  ambos desde el inicio (no dar por hecho un solo idioma al modelar contenidos o rutas).
- Documentación, commits y comunicación del repo en español.
- **Accesibilidad WCAG 2.2 nivel AA** como requisito no negociable, no como mejora posterior: contraste
  mínimo 4.5:1, foco visible en todo elemento interactivo, objetivos táctiles de 44×44px, etiquetas
  visibles en campos y estados que nunca se comuniquen solo con color.
- Color de acento expuesto como token `--acento` para poder recambiar la marca sin tocar componentes.
- **CRUD de artículos bilingüe atómico:** crear o editar un artículo exige español y portugués juntos; nunca
  se persiste un artículo en un solo idioma.
- **Acceso jerárquico estricto (`SuperAdmin ⊃ Administrador ⊃ Editor ⊃ Anonymous`):** la autorización se
  aplica **en el servidor**, no solo ocultando controles en la interfaz; un usuario nunca alcanza un recurso
  por encima de su nivel, ni por petición directa.
- **Aislamiento estricto entre portales (multi-tenant):** el `portal_id` se resuelve **del host de la
  petición en el servidor** y nunca del cliente; toda consulta filtra por él. Un usuario de un portal jamás
  ve ni alcanza datos de otro (acceso por id directo → **404**, no 403, para no revelar existencia). La
  sesión (cookie del BFF) se acota al host del portal y no autoriza en otro. SuperAdmin es la única
  identidad transversal a la plataforma.
- **`[Empresa]` es el identificador interno del campo de marca**, no un marcador de posición: se conserva
  tal cual en el modelo de datos, la API y las claves de código (p. ej. `guardarEmpresa`, rutas y esquemas).
  En la **interfaz de administración** ya no se muestra ese literal: el campo se rotula "Nombre de empresa"
  (pt "Nome da empresa") y los avisos de guardado y error muestran el valor que el administrador guardó
  (interpolado como `{{empresa}}`), no el texto `[Empresa]`. Con multi-tenant, ese valor es el
  `nombre_empresa` **del portal resuelto** (atributo del portal), no un ajuste global de la instalación.
- **Secretos fuera del repo:** cadena de conexión, secreto de firma JWT y credenciales de administrador van
  en variables de entorno (`.env` ignorado), con un `.env.example` sin valores reales.
- **Guardarraíles del chat generativo:** el chat público es Anonymous y NO responde nada fuera de los
  artículos/documentos indexados del portal resuelto por host. Separación estricta instrucción/dato: el
  prompt de sistema lleva solo reglas; consulta y fragmentos viajan como `role: user` dentro de un
  delimitador `<contenido_no_confiable_<nonce>>` con **nonce aleatorio por petición** (para que un atacante
  no pueda cerrar la etiqueta y reabrir instrucciones). El cliente **solo puede enviar turnos de
  `usuario`** en el historial (`TurnoChatIn`, schema); aceptar `asistente` permitiría inyectar un
  "asistente anterior" que el LLM trataría como contexto autoritativo. La salida del LLM se valida con
  Pydantic strict (`extra="forbid"`), y las citas se cruzan contra los fragmentos recuperados **y** el
  `portal_id` del host (defensa en profundidad frente a cita cruzada de portal → `sin_resultados`).
- **Proxies confiables (`X-Forwarded-*`):** el backend solo confía en `X-Forwarded-Host` (fuente del
  portal) y `X-Forwarded-For` (IP del cliente para el rate limit) cuando el peer inmediato está en la
  allow-list `PROXIES_CONFIABLES`. Sin esta comprobación, un cliente que llegase directo al puerto del
  backend podría suplantar el portal o colapsar toda la audiencia bajo la IP del proxy y disparar
  denegaciones cruzadas. Default `127.0.0.1,::1` (dev); en producción, la IP del reverse proxy y NADA más.
- **Licencia: MIT** (`LICENSE`, con `license: "MIT"` en `app/package.json` y `api/pyproject.toml`).
  Sustituye a la Business Source License 1.1 anterior: el código es libre de usar, modificar,
  redistribuir y revender (incluido como servicio hosteado) conservando el aviso de copyright y de
  licencia. Cualquier modelo comercial (open-core, funciones de pago) queda como decisión de producto,
  no codificada en la licencia.

Naming, formato, estrategia de tests y estructura de carpetas de código: _por definir._

## Estructura

```
app/                  Frontend Next.js (App Router)
  app/[idioma]/       Rutas por idioma: inicio, artículo, login, panel, usuarios, portales (SuperAdmin), error y 404
  app/api/            Route Handlers del BFF: auth, proxy de /api/admin/* con la cookie, y BFF Anonymous
                      del chat público en app/api/[idioma]/chat/consultar/route.ts (reenvía X-Forwarded-Host
                      + X-Forwarded-For sin adjuntar cookie)
  app/_bff/           Llamadas server-only al backend (login/refresh con reenvío de host) y sesionServidor()
                      para las guardias del panel; usado solo por los Route Handlers, nunca por el cliente
  app/_componentes/   Componentes de servidor y cliente de las pantallas de Next (incl. ChatWidget,
                      GestionPortales, panel/PanelSugerencias)
  app/_componentes/plantillas/documentacion/  Armazón de la plantilla de documentación (cabecera, navegación
                      lateral de la base de conocimiento, inicio y pie de página)
  proxy.ts            Guardia del panel en el borde + resolución de portal por host + CSP con nonce (antes middleware.ts)
  src/components/     Componentes reutilizados (Tabs, Modal, formularios, chips, iconos, acordeón)
  src/bff/            Cookies httpOnly, cliente del panel (apiFetch) y resolución de portal por host (portal.ts)
  src/seguridad/      Construcción de la CSP
  src/data/{es,pt}/   Contenido tipado por idioma (alimenta el seed y los tests de paridad, por portal)
  src/data/chat.ts    Cliente del BFF del chat, tipos (`TurnoChat`, `RespuestaChat`, veredicto discriminado)
                      y serializador de conversación para el mailto de escalamiento
  src/i18n/           i18next: traductor isomórfico, traducciones y rutas
  src/plantillas/     Resolución de la plantilla activa del portal (valor desconocido → `default`)
  src/types.ts        Contrato de datos
api/                  Backend FastAPI (modelos, routers, portales.py, admin_portales, auth, seed, tests, y
                      pipeline de chat en app/chat.py + app/recuperador.py + app/sesiones_chat.py +
                      app/cache_chat.py + app/persistencia_chat.py + app/routers/chat.py +
                      app/routers/admin_chats.py; harness EDD en tests/eval/ con dataset por idioma,
                      proveedor doble y baseline; sugerencias de artículo con IA en app/sugerencias.py +
                      app/routers/admin_sugerencias.py; ver api/README.md)
docker-compose.yml    PostgreSQL + pgvector (levanta la base de datos)
.claude/agents/       Subagentes de Claude Code: refactor-agent, security-reviewer, prompt-injection-reviewer,
                      test-writer
.claude/skills/       Skills de Claude Code: crear-pr (flujo de PR), auditar-accesibilidad, paridad-i18n
                      y los de OpenSpec
.cline/skills/        Los mismos skills de OpenSpec en el formato de Cline
.clinerules/workflows/  Los flujos de OpenSpec (opsx) como reglas de Cline: mismo cuerpo, cabecera de regla
                      en lugar de frontmatter de comando/skill
docs/architecture/    Diagramas C4 (contexto y contenedores) y ADR
docs/design/          Maqueta HTML de referencia de la plantilla de documentación
openspec/changes/     Cambios activos de OpenSpec (propuesta, diseño, specs, tareas)
openspec/changes/archive/  Cambios ya implementados y archivados
openspec/specs/       Especificaciones vigentes del sistema
```

Las pantallas consumen el contenido a través de `src/data/`: el público en servidor con
`src/data/servidor.ts` (Server Components) y el panel con `src/bff/apiFetch.ts` (BFF por cookie). Ese es el
punto por el que el contenido ficticio quedó sustituido por la API sin tocar componentes ni su ARIA.

El flujo de integración es `/crear-pr`: prepara rama, commit y Pull Request, y espera aprobación antes de
ejecutar nada.

### Índice de código (para optimizar tokens)

El repositorio está **indexado como grafo de conocimiento** por el servidor MCP `codebase-memory-mcp`
(se refresca en segundo plano). Para descubrir estructura de código —qué símbolos existen, quién llama
a qué, dependencias, fragmentos exactos— **usar primero sus herramientas de grafo** (`search_graph`,
`trace_path`, `get_code_snippet`, `query_graph`, `get_architecture`) en lugar de leer archivos enteros o
hacer `grep` amplios: devuelven solo lo pertinente y ahorran contexto. Se cae a lectura de archivos o
búsqueda por texto cuando la cobertura del grafo no basta o para texto no-código. Donde la herramienta lo
soporte, está disponible también como skill (`codebase-memory`) y como subagentes (`codebase-memory`,
`-auditor`, `-scout`). La cobertura es orientativa, nunca prueba de exhaustividad: verificar cada ruta
citada antes de afirmar sobre ella.

## Comandos

Desde `app/`:

```bash
npm install        # una sola vez
npm run dev        # servidor de desarrollo Next en http://localhost:3000
npm run build      # comprueba tipos y compila la app de producción (next build)
npm start          # sirve la compilación de producción (next start)
npm test           # tests con Vitest (una pasada)
npm run test:watch # tests en modo continuo
```

Se usa **npm**, no pnpm: pnpm no está instalado en la máquina de desarrollo. No hay linter. Todo `/api/*`
(contenido público, marca, auth y panel) lo atienden Route Handlers de Next que reenvían al backend
(`127.0.0.1:8000`) con el host del portal; no hay rewrites.

**Tests del frontend: Vitest, solo lógica pura.** Corren en entorno `node`, sin DOM: cubren `src/data/`,
`src/i18n/`, `src/types.ts`, `src/auth/nivel.ts`, `src/bff/cookies.ts`, `src/seguridad/csp.ts`,
`src/panel/panelPestanas.ts` y `src/plantillas/plantillas.ts`. Lo que necesita `fetch` lo sustituye por dobles en el propio test. Los
componentes y los Route Handlers **no** se prueban con Vitest: eso exigiría jsdom/Testing Library (o el
runtime de Next) y se decidió no introducirlos por ahora. Los archivos son `src/**/*.test.ts`, junto al
código que prueban.

`src/data/contenido.test.ts` es aparte: no prueba funciones sino **invariantes del contenido** de
`src/data/{es,pt}` (enlaces de `relacionados`, citas del chat, fechas ISO, paridad es/pt). Ese contenido
alimenta el seed del backend, así que un artículo en un solo idioma se propagaría a la API. Está escrito
para que añadir o traducir artículos no lo rompa; olvidarse de un idioma sí.

La configuración vive en **`vitest.config.ts`**. Vitest necesita Vite instalado (por eso `vite` sigue en
`devDependencies` aunque ya no haya empaquetado de Vite propio); corre en entorno `node` y solo resuelve el
alias `@` → `src`, sin plugins de React ni Tailwind, porque prueba `.ts` sin JSX.

Backend (desde `api/`, con la base de datos levantada por `docker compose up -d`):

```bash
pip install -e ".[dev]"                 # dependencias (en un entorno virtual)
alembic upgrade head                    # esquema + extensión pgvector
node ../app/scripts/exportar-datos.mjs  # exporta el contenido TS a JSON para el seed
python seed.py                          # carga el contenido y siembra el admin
uvicorn app.main:app --reload           # API en http://localhost:8000
pytest                                  # pruebas del backend (SQLite en memoria)
```

El detalle está en `api/README.md`. En desarrollo hay que tener los tres procesos vivos: `docker compose
up -d` (Postgres), `uvicorn` en `api/` y `npm run dev` en `app/`. `api/.env` debe fijar
`BASE_DOMAIN=localhost` en desarrollo: sin eso, un portal creado desde el panel siembra su
subdominio bajo el default de producción (`tuapp.com`) y no resuelve en el navegador; con
`localhost` sí (p. ej. `aviacion.localhost`).

## Reglas

- **Todo comando lo aprueba o lo ejecuta la persona desarrolladora.** El agente no ejecuta comandos por su
  cuenta: los propone y espera aprobación explícita, o los deja escritos para que se ejecuten a mano. Esto
  incluye instalaciones, scripts, herramientas de compilación y cualquier operación de git.
- **Ante ambigüedad en un prompt, entrar de inmediato en modo entrevista.** Si el encargo admite lecturas
  que llevarían a trabajos distintos, el agente pregunta antes de avanzar en lugar de elegir una
  interpretación y seguir. No se resuelve la duda con suposiciones.
- **No se hace commit directo.** Los cambios se integran mediante Pull Request, y el flujo se ejecuta a
  través del skill `/crear-pr` (`.claude/skills/crear-pr`), nunca con comandos de git sueltos. Tampoco se
  hace push a `main`.
- **No asumir el stack.** El stack del backend ya está decidido (FastAPI + PostgreSQL/pgvector + auth
  argon2/JWT; ver Stack › Backend), pero cualquier framework, dependencia o estructura **nuevos** se
  preguntan antes de introducirlos.
- Mantener este archivo actualizado a medida que se definan stack, comandos y convenciones, y
  **sincronizado con `CLAUDE.md`** (el mismo contenido, en lenguaje neutro de herramienta).
