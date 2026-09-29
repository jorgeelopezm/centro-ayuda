# Backend — Centro de Ayuda API

FastAPI + PostgreSQL (pgvector). Sirve el contenido bilingüe, el CRUD de artículos, la autenticación del
panel interno, la ingesta RAG por portal, el **chat generativo con RAG por portal** (cambio OpenSpec
`chat-rag-portal`) y la **generación asistida por IA de borradores de artículo** a partir de chats
escalados, preguntas sin resolver y huecos de documentación RAG (cambio OpenSpec `sugerir-articulos-ia`).
Es **multi-tenant por portal** (cambio OpenSpec `multi-tenant-portales`): una sola
instalación sirve a varios clientes discriminando todos los datos por `portal_id`, y el portal se resuelve
**del host de la petición** (ver "Resolución de portal y proxy de confianza"). El control de acceso tiene
cuatro niveles jerárquicos `SUPERADMIN=4 > ADMINISTRADOR=3 > EDITOR=2 > ANONIMO=1`; `requiere_nivel` exige
nivel suficiente **y** pertenencia al portal del host (recurso de otro portal por id directo → 404).

## Arranque diario (cada sesión)

Lo único que hay que hacer cada día para levantar el backend. Los datos persisten en el volumen de Docker,
así que **no** hay que volver a migrar ni sembrar.

```powershell
# Desde la raíz del repo
docker compose up -d                    # 1. arranca Postgres (los datos siguen ahí)

cd api
.venv\Scripts\Activate.ps1              # 2. activa el entorno virtual (PowerShell)
uvicorn app.main:app --reload           # 3. API en http://localhost:8000  (docs en /docs)
```

En otra terminal, el frontend (sus Route Handlers reenvían `/api/*` al backend, sin rewrite, para poder
adjuntar el host del portal):

```powershell
cd app
npm run dev                             # http://localhost:3000
```

Para parar al final del día: `Ctrl+C` en cada terminal y, si se quiere, `docker compose stop`.
**Importante:** nunca uses `docker compose down -v` — el `-v` borra el volumen y con él todos los datos.

## Configuración inicial (una sola vez)

Estos pasos ya no se repiten salvo cambios (nueva migración, cambio de contenido o reinicio de la base).

```powershell
docker compose up -d                              # base de datos (Postgres + pgvector)

cd api
python -m venv .venv                              # crear el entorno virtual
.venv\Scripts\Activate.ps1                        # (Git Bash: source .venv/Scripts/activate)
pip install -e ".[dev]"                           # dependencias del backend

copy .env.example .env                            # y ajustar JWT_SECRET y ADMIN_PASSWORD

alembic upgrade head                              # esquema + extensión vector
node ../app/scripts/exportar-datos.mjs            # contenido TS → JSON (o, en app/: npm run exportar-datos)
python seed.py                                    # carga el contenido y siembra el admin
```

Cuándo repetir algún paso de esta sección:

- **Nueva migración** → `alembic upgrade head`.
- **Cambió el contenido de `app/src/data`** → `node ../app/scripts/exportar-datos.mjs` y `python seed.py`.
- **Quieres resetear la base** → `docker compose down -v` (borra datos) y repetir esta sección entera.

## Pruebas

```powershell
cd api
.venv\Scripts\Activate.ps1
pytest                                            # SQLite en memoria, no requiere Postgres
```

Los tests marcados con `@pytest.mark.eval` (harness EDD del chat) NO se ejecutan por
defecto (`-m` no incluye `eval`). Ver la sección de [evaluación del chat](#evaluación-eval-driven-del-chat-con-rag)
para el modo `ci` (dobles deterministas) y el modo `real` (proveedor real, opt-in).

## Poblado inicial del índice RAG de artículos

Tras aplicar la migración `0008_rag_chunks` (que crea `documentos`,
`documento_chunks` y `articulo_chunks`), los **artículos existentes** no tienen
todavía fragmentos indexados: el hook automático de `admin_articulos.py` solo
cubre altas y ediciones a partir de ese momento. Para llenar el índice con los
artículos que ya estaban:

```powershell
cd api
.venv\Scripts\Activate.ps1
python reindexar_articulos.py
```

Recorre todos los portales y todos sus artículos y regenera fragmentos e
embeddings usando el proveedor configurado en `ConfigIA` (Voyage AI por
defecto, u OpenAI si SuperAdmin lo reconfiguró desde el panel de IA). Es **idempotente**:
volver a correrlo no duplica nada. También sirve como operación de
mantenimiento si se cambia el modelo de embeddings (`EMBEDDING_DIM`).

## Chat generativo con RAG por portal

Endpoint público Anonymous `POST /api/{idioma}/chat/consultar` (`app/routers/chat.py`). El pipeline
(`app/chat.py::responder`) responde SOLO con base en los fragmentos indexados del portal resuelto por
host:

1. **Validación estructural** (schema `ChatConsultaIn`): consulta con longitud acotada
   (`CHAT_MAX_CONSULTA_CHARS`), historial con máximo 50 turnos y **solo `rol: usuario`** (schema
   `TurnoChatIn`; aceptar `asistente` permitiría inyectar un "asistente falso" que el LLM trataría como
   contexto autoritativo). Cualquier `portal_id` en el cuerpo se ignora.
2. **Interruptor de mantenimiento** (`CHAT_HABILITADO=false` → 503) y **límite de tasa por IP** con
   ventana deslizante en memoria (`CHAT_LIMITE_TASA_MIN` req/min, dict acotado a 10 000 IPs con purga
   perezosa).
3. **Corto-circuito `solicitar_soporte: true`** → `veredicto: escalar`, `razon: solicitud_usuaria`, sin
   llamar al proveedor.
4. **Clasificador de scope** (LLM, temperatura 0, ~5 tokens): `EN_SCOPE` / `FUERA_DE_SCOPE`. Si la salida
   es otra, se asume `EN_SCOPE` (política conservadora). `FUERA_DE_SCOPE` → rechazo sin recuperar ni
   generar.
5. **Recuperación vectorial** (`app/recuperador.py::recuperar`): embedding de la consulta con Voyage AI
   por defecto, búsqueda en `articulo_chunks` (filtrada por `portal_id` **e** `idioma`) unida con
   `documento_chunks` (filtrada por `portal_id`), coseno pgvector (o cálculo en Python bajo SQLite para
   los tests), umbral `RAG_UMBRAL_SIMILITUD` y tope `RAG_TOP_K`. Sin fragmentos por encima del umbral →
   `sin_resultados`; el contador de la sesión (`app/sesiones_chat.py`) se incrementa y a los
   `CHAT_UMBRAL_TURNOS_SIN_RESULTADOS` seguidos escala con `razon: tope_turnos`.
6. **Generación con JSON estricto**: `role: system` con reglas + formato; `role: user` con cada turno
   histórico envuelto en el delimitador; `role: user` con la consulta y los fragmentos numerados.
7. **Validación de la salida**: parseo Pydantic `extra="forbid"`; cada `[n]` citada existe en los
   fragmentos entregados **y** pertenece al `portal_id` del host (defensa en profundidad contra cita
   cruzada); ante fallo → `sin_resultados`. `respondida` resetea el contador de la sesión.
8. **Ninguna salida cruda del LLM llega al cliente**: los errores del proveedor caen a
   `veredicto: escalar razon: error_proveedor` con mensaje bilingüe genérico.

### Guardarraíles contra inyección de prompts

- **Separación instrucción/dato**: prompt de sistema con solo reglas; consulta, historial y fragmentos
  como `role: user` dentro de `<contenido_no_confiable_<nonce>>` con **nonce aleatorio por petición**
  (`secrets.token_urlsafe`). Un atacante que quiera cerrar la etiqueta necesitaría adivinar el nonce.
- **Saneo del literal base**: `_sanear()` elimina cualquier ocurrencia de `</?contenido_no_confiable*>`
  del texto no confiable (belt + suspenders sobre el nonce).
- **Historial de solo usuario** en el schema (`TurnoChatIn`); la conversación completa con turnos de
  asistente sigue viajando de vuelta al cliente en `RespuestaChat.conversacion` para el mailto de
  escalamiento, serializada en el servidor.
- **Aislamiento por portal end-to-end**: `portal_id` resuelto del host + validación de citas contra
  `portal_id` del fragmento; el schema del recuperador filtra por `portal_id` en cada consulta a pgvector.

Persistir el historial server-side ligado a `session_id` (para prescindir del envío de historial por
parte del cliente) queda para el cambio posterior `historial-chat-server`.

### Configuración de proveedores de IA

`ConfigIA` (singleton) tiene **un campo por rol** de IA: `proveedor_chat`, `proveedor_traduccion` y
`proveedor_embeddings` (todos nullable; `NULL` = usar el default codificado del rol). Las claves de API
viven en la tabla `config_ia_clave` (una fila por proveedor, cifrada con Fernet), no dentro de `ConfigIA`.
Motores implementados hoy: **chat** con DeepSeek (OpenAI-compatible); **traducción** con Anthropic o
DeepSeek; **embeddings** con Voyage AI (default, recomendado por Anthropic) o cualquier otro proveedor
OpenAI-compatible (p. ej. OpenAI). SuperAdmin configura cada rol por separado en el panel: los
selectores se filtran contra el mapa `rolesSoportados` que devuelve el propio backend (el `PUT` rechaza
con 422 cualquier asignación de rol → proveedor sin motor real). Borrar la clave de un proveedor en uso
por algún rol responde 409. Ver cambio OpenSpec `separar-proveedores-ia`.

## Sugerencias de artículo asistidas por IA

Router `app/routers/admin_sugerencias.py`, pipeline `app/sugerencias.py` (spec OpenSpec
`sugerir-articulos-ia`). Todos los endpoints exigen `requiere_nivel(EDITOR)` y filtran por el `portal_id`
del host; acceso cruzado por id → 404.

- **Tres agregadores por portal** (`app/sugerencias.py`), cada uno produce candidatos `Candidato` con
  `fuente`, `referencia`, `titulo_sugerido`, `idioma`, `prioridad` y `ya_generada`:
  1. `chat_escalado`: agrupa `chat_interaccion` con `veredicto=escalar` por consulta normalizada;
     prioridad = nº de escalados.
  2. `pregunta_sin_resolver`: une `preguntas_sin_resolver` con las interacciones `veredicto=sin_resultados`;
     prioridad por frecuencia.
  3. `documentacion_rag`: fragmentos de documentos `listo` sin artículo que los cubra (recuperación
     inversa con umbral de distancia); prioridad = tamaño del hueco.
- **Generación bajo demanda, no en lote:** cada candidato se genera solo cuando la persona editora lo pide
  explícitamente; controla el gasto de IA. `generar_borrador()` recupera fragmentos del portal
  (`app/recuperador.py`), redacta en español con `proveedor_chat` (JSON estricto, Pydantic `extra="forbid"`),
  completa el portugués con `proveedor_traduccion` (reutiliza `app/servicios.py`), y cruza las citas contra
  los fragmentos recuperados **y** el `portal_id` del host — mismos guardarraíles de separación
  instrucción/dato y nonce por petición que el chat (ver sección anterior). No se añaden roles nuevos a
  `ConfigIA`: reutiliza `proveedor_chat` y `proveedor_traduccion` ya configurados.
- **La sugerencia nunca es pública:** se persiste en `sugerencia_articulo` (migración `0013`) en estado
  `pendiente`, con `contenido` bilingüe, `citas`, proveedores y modelo usados. No crea artículo, no entra
  al índice RAG, no aparece en el centro de ayuda ni en el chat.
- **Endpoints:**
  - `GET /api/admin/sugerencias/candidatos?fuente=` — candidatos agregados del portal (fuente opcional).
  - `POST /api/admin/sugerencias/generar` (`{fuente, referencia}`) — dispara el pipeline; idempotente si
    ya existe una sugerencia `pendiente` para ese `(portal_id, fuente, referencia)` (devuelve la existente
    sin gastar IA de nuevo).
  - `GET /api/admin/sugerencias` — cola de sugerencias `pendiente`.
  - `GET /api/admin/sugerencias/{id}` — detalle bilingüe para precargar el formulario.
  - `POST /api/admin/sugerencias/{id}/aceptar` (contenido editable) — crea el artículo por el alta
    existente (bilingüe atómico + re-indexado RAG) y marca `aceptada` con `articulo_id`; contenido
    incompleto → 422 sin marcar `aceptada`.
  - `POST /api/admin/sugerencias/{id}/descartar` — marca `descartada` sin crear artículo.
- **Frontend:** pestaña "Sugerencias" del panel interno (nivel ≥ Editor), entre "Chats" y "Categorías";
  reutiliza el modal de formulario de artículo existente para la revisión y el alta.

## Resolución de portal y proxy de confianza (multi-tenant)

El backend es **multi-tenant por host**: cada petición se atribuye a un portal (tenant) resolviendo su
**host**, y esa es la **única** fuente del portal. Nunca se toma de un parámetro de ruta/query, del cuerpo,
ni de una cabecera de aplicación que pueda fijar el cliente (`deps.py::portal_actual` →
`portales.py::resolver_portal`). Un host desconocido responde `404` y un portal suspendido `503`; jamás se
sirve el contenido de otro portal ni el de un portal por defecto.

### Cómo llega el host al backend

El frontend de Next es el **proxy inmediato** del backend. Como sus llamadas van al origen interno
(`127.0.0.1:8000`), el `Host` que vería el backend sería ese origen interno, que no identifica ningún
portal. Por eso Next reenvía el host del navegador en **`X-Forwarded-Host`** (`app/src/bff/portal.ts`), y el
backend lo **prefiere** sobre `Host` (`deps.py::_host_de_confianza`, tomando solo el primer valor de la
lista, el del cliente). En llamadas directas sin proxy (p. ej. los tests) se cae a `Host`.

### Configuración del proxy de confianza (producción) — evitar suplantación de portal

`X-Forwarded-Host` y `X-Forwarded-For` son **suplantables por definición**: cualquier cliente puede
enviarlos. El backend solo los honra cuando el peer inmediato (`request.client.host`) está en la lista
`PROXIES_CONFIABLES` (`config.py::proxies_confiables_set`). Sin esa allow-list, un cliente que llegase
directo al puerto del backend podría suplantar el portal (fabricando `X-Forwarded-Host`) o **colapsar
todo el rate limit** bajo la IP del proxy (fabricando `X-Forwarded-For`) y disparar denegaciones cruzadas
entre visitantes que no se conocen. Configuración requerida al desplegar:

1. **El backend no se expone a Internet.** Escucha en loopback o en una red privada; el único que puede
   llegar a él es el frontend de Next (Route Handlers del BFF). Si el backend fuera público, un cliente
   podría mandar `X-Forwarded-Host: portal-victima.tuapp.com` y leer/escribir en el portal de otro.
2. **`PROXIES_CONFIABLES` contiene EXACTAMENTE la IP del reverse proxy** (nginx/traefik/CDN) y nada más.
   Default `127.0.0.1,::1` sirve para desarrollo local (Next → uvicorn en la misma máquina). Cualquier
   petición cuyo peer no esté aquí ve ignoradas las cabeceras: cae a `Host` para el portal y al socket
   para la IP del rate limit.
3. **El borde reescribe `X-Forwarded-Host` desde el `Host` real y añade `X-Forwarded-For` con la IP del
   cliente**, sin propagar los valores que mandara el cliente: `cabecerasPortal()` y el BFF del chat en
   `app/api/[idioma]/chat/consultar/route.ts` los construyen a partir del `Host` y de la IP entrantes de
   confianza. Si se antepone otro proxy (CDN/balanceador), debe **descartar** cualquier
   `X-Forwarded-Host`/`X-Forwarded-For`/`X-Forwarded-*` entrante del cliente y ponerlo él.
4. **Un solo salto de confianza.** Se lee solo el primer valor de las cabeceras `X-Forwarded-*`; no se
   encadenan proxies que añadan saltos no confiables antes del borde.

Con esas cuatro condiciones, el host efectivo es siempre el que el proveedor asignó al portal y la IP
del rate limit es siempre la del visitante real, no un valor elegido por el cliente. El comodín TLS
`*.tuapp.com` y el diseño de dominios propios (ACME por dominio) quedan como fase posterior (ver
`infraestructura-despliegue`).

## Evaluación (Eval-Driven) del chat con RAG

Harness EDD en `tests/eval/` (spec `evaluacion-chat-rag`) para medir la calidad
del pipeline del chat contra un dataset versionado, con dos modos:

- **`ci`** (por defecto): dobles deterministas. No hace llamadas de red ni
  requiere clave. Prueba el pipeline end-to-end (scope, recuperación,
  validación de citas, formato) con métricas comparables entre PRs.

  ```powershell
  cd api
  .venv\Scripts\Activate.ps1
  pytest -m eval                                   # ejecuta el harness modo ci
  ```

- **`real`** (opt-in): apunta al proveedor real configurado en `ConfigIA`
  (DeepSeek/Anthropic + Voyage/OpenAI) y añade `latencia_media_ms` y
  `coste_total_usd_estimado`. Requiere flag `--real` **y**
  `CHAT_EVAL_HABILITADO_REAL=1` para no dispararse por accidente con coste.

  ```powershell
  $env:CHAT_EVAL_HABILITADO_REAL = "1"
  pytest -m eval --real                            # ejecuta el harness modo real
  ```

Cada corrida escribe `tests/eval/reports/last.json` con métricas globales y
por idioma, más el resultado por caso (`id`, `veredicto_obtenido`,
`citas_obtenidas`, `longitud`, `latencia_ms`, ...).

**Gate contra baseline.** El harness compara la corrida contra
`tests/eval/baseline.json` y falla el test si alguna métrica cae bajo su
umbral (por defecto: `exactitud_veredicto ≥ baseline - 0.02`,
`precision_citas ≥ baseline - 0.02`, `pasos_en_formato_correcto ≥ baseline -
0.02`, `longitud_media ≤ baseline * 1.10`). Al mejorar una métrica en una PR,
actualiza `baseline.json` en la misma PR para que el gate proteja el nuevo
suelo (spec `evaluacion-chat-rag`).

**Añadir un caso al dataset.** Cada línea de `tests/eval/casos_{es,pt}.jsonl`
es un JSON con `id`, `consulta`, `portal`, `idioma`, `veredicto_esperado` y,
para `respondida`, `citas_esperadas_por_slug` (lista con al menos un slug).
Los campos opcionales son `longitud_max`, `debe_contener_pasos`, `adversario`,
`solicitar_soporte` (para casos `escalar` por solicitud del usuario) y
`respuesta_texto` (respuesta que el proveedor doble devuelve; con
`veredicto_esperado="respondida"`). El dataset se revisa en PR como cualquier
otro fichero fuente.

## Variables de entorno

Todas viven en `.env` (nunca en el repo) con la lista comentada en `.env.example`. Las obligatorias sin
default son las que codifican secretos (`JWT_SECRET`, `ADMIN_PASSWORD`). El resto tiene default sensato
en `config.py::Settings`. Grupos:

- **Base**: `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`,
  `SUPERADMIN_EMAIL`, `SUPERADMIN_PASSWORD` (opcional), `EMPRESA_INICIAL`, `BASE_DOMAIN` (en
  desarrollo, fijar `localhost`: así los subdominios que crea el panel de Portales, p. ej.
  `aviacion.localhost`, resuelven en el navegador sin tocar hosts/DNS; el default de
  `config.py`, `tuapp.com`, es el valor de producción), `CLAVE_CIFRADO_IA` (Fernet, cifra las
  claves de los proveedores de IA en `ConfigIA`).
- **Chat + RAG** (todas con default): `RAG_UMBRAL_SIMILITUD` (0.28, calibrado para `voyage-3`),
  `RAG_TOP_K` (6), `CHAT_MAX_CONSULTA_CHARS` (500), `CHAT_MAX_HISTORIAL_TURNOS` (10),
  `CHAT_UMBRAL_TURNOS_SIN_RESULTADOS` (2), `CHAT_TTL_SESION_SEG` (1800), `CHAT_LIMITE_TASA_MIN` (30),
  `CHAT_HABILITADO` (true), `CHAT_PERSISTENCIA_HABILITADA` (true; escribe cada interacción en
  `chat_interaccion` para el panel de supervisión), `CHAT_LONGITUD_MAX_CHARS` (1400; recorte suave
  aplicado solo al veredicto `respondida`), `CHAT_CACHE_HABILITADA` (true), `CHAT_CACHE_TTL_SEG` (600),
  `CHAT_CACHE_MAX_ENTRADAS` (1000).
- **Eval del chat** (solo relevante en el modo `real` del harness): `CHAT_EVAL_HABILITADO_REAL` (1
  para permitir `pytest -m eval --real`; cualquier otro valor salta los casos reales con `pytest.skip`).
- **Proxies confiables** (default `127.0.0.1,::1`): `PROXIES_CONFIABLES`. Ver sección anterior.

## Estructura

```
app/
  main.py            App FastAPI y montaje de routers
  config.py          Configuración por entorno (pydantic-settings); expone `proxies_confiables_set`
  database.py        Motor, sesión y Base declarativa
  models.py          Modelos SQLAlchemy (patrón bilingüe; Portal + portal_id en todas las entidades;
                     ConfigIA con proveedor_chat/_traduccion/_embeddings + modelo_chat/temperatura_chat;
                     ConfigIAClave con la clave cifrada por proveedor, una fila por proveedor)
  schemas.py         Esquemas Pydantic (reproducen app/src/types.ts). `TurnoChatIn` (solo rol usuario,
                     input del chat) vs `TurnoChat` (ambos roles, output para la conversación)
  security.py        Hash argon2 + JWT; enum de niveles (SUPERADMIN..ANONIMO)
  deps.py            Dependencias: admin_actual, requiere_nivel, portal_actual (host → portal) con
                     `_peer_confiable` gateando X-Forwarded-Host por la allow-list de PROXIES_CONFIABLES
  portales.py        Resolución host → portal (dominios, subdominio base, slugs reservados)
  servicios.py       Ensamblado de contenido y escritura de artículos (acotado al portal)
  servicios_ia.py    ProveedorTraduccion (Anthropic/DeepSeek), ProveedorEmbeddings (Voyage/OpenAI),
                     ProveedorChat (DeepSeek); factories `crear_chat`/`crear_embedder`/`crear_proveedor`
  cifrado.py         Fernet para cifrar/descifrar las claves de API guardadas en ConfigIA
  chat.py            Pipeline del chat: `responder()`, clasificador de scope, generación con JSON estricto,
                     delimitador con nonce aleatorio, validación de citas contra portal_id
  recuperador.py     Recuperador vectorial acotado al portal (pgvector coseno + fallback SQLite en tests)
  sesiones_chat.py   Sesiones efímeras en memoria con TTL para el contador de turnos_sin_resultados
  ingesta.py         Ingesta RAG: troceo → embedding → escritura de articulo_chunks/documento_chunks
  troceo.py          Trocea contenido de artículo/documento en fragmentos con solape controlado
  rag.py             Constantes del RAG (dimensión, modelo, URL base de embeddings)
  sugerencias.py     Pipeline de sugerencias de artículo con IA: los tres agregadores (chat_escalado,
                     pregunta_sin_resolver, documentacion_rag) y generar_borrador() (redacción bilingüe +
                     cruce de citas por portal)
  routers/           contenido, comun, marca, auth, admin_articulos, admin_categorias, admin_usuarios,
                     admin_ajustes, admin_config_ia, admin_panel, admin_portales (gestión SuperAdmin),
                     admin_documentos (ingesta RAG por portal), admin_chats (supervisión: GET
                     /api/admin/chats, /{chat_id}, /metricas), admin_sugerencias (candidatos/generar/
                     listar/detalle/aceptar/descartar) y chat (POST /api/{idioma}/chat/consultar,
                     Anonymous, rate limit por IP con allow-list de proxies confiables)
alembic/             Migraciones (0001…0014: la 0008 crea las tablas del RAG, la 0009 añade modelo_chat
                     y temperatura_chat a config_ia, la 0012 hace UUID el id de portal, la 0013 crea
                     sugerencia_articulo y la 0014 quita `fondo`/`texto` de categorias)
seed.py              Carga seed_data/*.json bajo el portal `default` y siembra su Administrador
reindexar_articulos.py  Reindexa el RAG de artículos existentes (idempotente)
tests/               pytest (contenido, auth, refresh, niveles, CRUD de artículos/categorías/usuarios,
                     ajustes, marca, aislamiento, portales, portales_gestion, chat_endpoint,
                     chat_pipeline, chat_recuperador, admin_chats, brevedad_chat, cache_chat,
                     persistencia_chat, config_ia, traducción (artículos y categorías), troceo,
                     contraste, security, sugerencias_agregadores, sugerencias_pipeline,
                     admin_sugerencias, admin_documentos, admin_panel)
tests/eval/          Harness EDD del chat con RAG: dataset `casos_{es,pt}.jsonl`, proveedor doble,
                     `test_eval_chat.py` (marker `eval`, modos `ci` y `real`), `baseline.json` con
                     los umbrales del gate y `reports/last.json` (última corrida)
```
