# ADR-0001: PostgreSQL con pgvector como base de datos única

**Estado:** Aceptada. **Confirmada en producción por el RAG** (cambios OpenSpec `rag-ingesta` y
`chat-rag-portal`, archivados 2026-08-18): ya no es una apuesta, es la base de datos vectorial real del
chat y las sugerencias de artículo.

## Contexto

El backend del Centro de Ayuda (`api/`) persiste dos cosas de naturaleza muy distinta: el contenido
relacional bilingüe (categorías, artículos, traducciones, preguntas sin resolver, métricas, usuarios
administradores, portales) y los vectores del sistema de recuperación aumentada por generación (RAG) que
alimenta el chat público y las sugerencias de artículo asistidas por IA. En el momento de esta decisión el
alcance era "API de contenido + CRUD de artículos + auth; RAG solo diseñado, no construido"; hoy el RAG
está construido y en uso (ver `CLAUDE.md`, secciones "Chat con RAG por portal" y "Sugerencias de artículo
asistidas por IA").

Restricción de negocio que motivó la decisión: el RAG era la siguiente pieza del roadmap, no una
hipótesis lejana — se eligió Python para el backend "por el RAG futuro". Introducir un motor de datos
distinto cuando llegara esa fase habría implicado reescribir el modelo de persistencia y migrar todo el
contenido ya sembrado.

La evidencia en código confirma que la decisión se tomó temprano y se sostuvo: `docker-compose.yml`
levanta un único servicio de base de datos con la imagen `pgvector/pgvector:pg16`; la primera migración
de Alembic ejecuta `CREATE EXTENSION IF NOT EXISTS vector` (`api/alembic/versions/0001_inicial.py`); y
`api/app/config.py` fija por defecto la cadena de conexión `postgresql+psycopg://...`. Desde la migración
`0008_rag_chunks`, dos tablas usan el tipo `vector`: `documento_chunks` (fragmentos de documentos subidos
para el índice RAG, `api/app/ingesta.py`) y `articulo_chunks` (fragmentos de artículos, uno por idioma).
Ambas las consulta `api/app/recuperador.py` por distancia coseno (`cosine_distance` del `Comparator` de
`pgvector.sqlalchemy.Vector`) para responder el chat y detectar huecos de documentación en
`api/app/sugerencias.py`.

## Decisión

Adoptamos PostgreSQL con la extensión `pgvector` como única base de datos del sistema, habilitada desde
la primera migración, antes de que existiera ningún caso de uso de RAG. Todo el contenido relacional y los
embeddings de artículos y documentos viven en el mismo motor, sin una base de datos vectorial separada.

## Alternativas consideradas

- **SQLite.** Descartada explícitamente en el diseño del cambio `backend-cms-autenticacion`: su soporte
  vectorial (`sqlite-vec`) es menos estándar que `pgvector`, y probablemente forzaría una migración a
  Postgres justo cuando llegue el RAG — el motivo documentado es evitar pagar dos veces el coste de
  migración (`openspec/changes/backend-cms-autenticacion/design.md`, referenciado desde `CLAUDE.md`).
  SQLite sí se usa hoy, pero solo en los tests (`api/tests/conftest.py`), nunca como base de producción.
- **Base de datos vectorial separada** (p. ej. un servicio dedicado de embeddings, desacoplado del
  almacén relacional). Es la alternativa habitual en arquitecturas RAG que no colocan los vectores en el
  mismo motor que el resto de los datos. TODO: confirmar — no hay ningún documento ni commit en el
  repositorio que registre por qué se descartó esta opción frente a pgvector; la razón más probable es
  evitar un segundo sistema que sincronizar y operar, pero no está documentada.

## Consecuencias

**Positivas:** la predicción se cumplió — no hizo falta ninguna migración de motor cuando se construyó el
RAG (`rag-ingesta`, `chat-rag-portal`), solo migraciones incrementales de esquema (`0008_rag_chunks` en
adelante) sobre la misma base ya desplegada. Un solo sistema que desplegar, respaldar y operar, en vez de
dos: el contenido, la administración, la config de IA (`config_ia`, `config_ia_clave`), la traza de chats
(`chat_interaccion`) y ahora los embeddings comparten motor y transacciones — un documento y sus
fragmentos se insertan o revierten juntos (`api/app/ingesta.py`), algo mucho más costoso de garantizar
con dos sistemas separados. El modelo de datos usa el mismo patrón para ambos tipos especiales:
`JSON().with_variant(JSONB(), "postgresql")` para JSON y `Vector(EMBEDDING_DIM).with_variant(JSON(),
"sqlite")` para vectores (`api/app/models.py`), aprovechando JSONB/pgvector nativos en producción sin
perder la compatibilidad con SQLite en los tests.

**Negativas / deuda técnica:** los tests del backend corren contra SQLite en memoria
(`api/tests/conftest.py`), nunca contra Postgres real, así que la distancia coseno de `pgvector` y el
índice HNSW **no se ejercitan en la suite de pruebas** — en SQLite `VectorType` degrada a `JSON` y
`api/app/recuperador.py` calcula la similitud en Python en vez de en la base de datos (fallback
documentado en `CLAUDE.md`). Los tests cubren troceo, estado y aislamiento por portal con dobles del
proveedor de embeddings, no el comportamiento vectorial real de Postgres; ese camino solo se verifica en
desarrollo/producción o con `pytest -m eval --real` contra la base real. La función `downgrade()` de la
migración inicial no revierte la extensión `vector` (`api/alembic/versions/0001_inicial.py`), así que
revertir esta decisión por completo exigiría una migración manual adicional. Cambiar de modelo de
embeddings (hoy `voyage-3`, 1024 dims, fijado en `api/app/rag.py`) no tiene migración automática: exige
actualizar `EMBEDDING_DIM`, una migración de esquema y re-embeber todo el contenido existente.
