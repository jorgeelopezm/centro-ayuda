# ADR-0002: Multi-tenant por `portal_id` (UUID) en aplicación, sin Row-Level Security

**Estado:** Aceptada e implementada (cambio OpenSpec `multi-tenant-portales`, archivado 2026-08-17).

## Contexto

El Centro de Ayuda pasó de single-tenant (una instalación, una marca, contenido y usuarios globales) a
atender **varios clientes con un solo código y una sola base de datos**, cada uno con su propia URL, marca
y usuarios. La restricción de negocio que motivó el diseño fue explícita en la entrevista del cambio
`multi-tenant-portales`: minimizar el mantenimiento de varios portales a la vez — una sola instalación que
operar, respaldar y desplegar, en vez de una por cliente
(`openspec/changes/archive/2026-08-17-multi-tenant-portales/design.md`).

Para aislar los datos de cada portal dentro de esa base compartida había que decidir dos cosas
independientes: (1) el modelo de particionado — base/esquema por cliente frente a base compartida con un
discriminador — y (2) el mecanismo de aislamiento — quién garantiza que una consulta de un portal nunca
toque filas de otro. La primera se resolvió por *shared database, shared schema*; la segunda es el objeto
de este ADR: filtrado por `portal_id` en la capa de aplicación, no Row-Level Security (RLS) de PostgreSQL.

La evidencia en código confirma la decisión: `Portal.id` es `uuid.UUID` (`api/app/models.py`), y
`portal_id` es una columna `uuid.UUID` presente como FK en cerca de quince tablas de contenido y usuarios
(categorías, artículos, sus traducciones, artículos relacionados, chunks RAG, chats, sugerencias, etc.).
En las tablas de contenido, `portal_id` forma parte de la **clave primaria compuesta**
(`PrimaryKeyConstraint("portal_id", "id")`) en vez de dejar el `id` único de forma global — así el id de
un artículo o categoría es único *por portal*, no en toda la instalación, y las FKs compuestas
(`["portal_id", "categoria_id"], ["categorias.portal_id", "categorias.id"]`) obligan a que ambos extremos
de una relación pertenezcan al mismo portal. El aislamiento se aplica en `requiere_nivel`, que ya resolvía
la autorización jerárquica en servidor, extendido para exigir además pertenencia al portal del host; un
acceso cruzado por id directo responde **404**, no 403, para no revelar la existencia del recurso en otro
portal. No hay `SET app.portal_id`, políticas `POLICY` ni ninguna otra pieza de RLS en las migraciones de
Alembic.

## Decisión

Aislamos los portales dentro de la misma base de datos con un discriminador `portal_id` de tipo **UUID**,
resuelto **en el servidor a partir del host de la petición** (nunca del cliente) y aplicado por **toda**
consulta en la capa de aplicación — dependencias/repositorio + índices y claves compuestas —, sin recurrir
a Row-Level Security de PostgreSQL.

## Alternativas consideradas

- **Base de datos o esquema por cliente** (*database-per-tenant* / *schema-per-tenant*). Ofrecen mayor
  aislamiento nativo, pero multiplican las migraciones (una por cliente) y, en el caso de esquema por
  tenant, complican el *pooling* de conexiones. Ambas contradicen directamente el objetivo declarado de
  "una sola instalación, una sola base de datos" y fueron descartadas en el diseño (D1 de
  `design.md`).
- **Row-Level Security de PostgreSQL** como mecanismo primario de aislamiento. Habría añadido una pieza de
  infraestructura nueva —`SET app.portal_id` por sesión de conexión y políticas `POLICY` por tabla— sin
  necesidad inmediata, porque la autorización por servidor (`requiere_nivel`) ya existía y ya resolvía el
  problema equivalente para los niveles de acceso; introducirla habría sido una dependencia operativa
  adicional para un proyecto de este tamaño, no una simplificación (D2 de `design.md`). Se descartó
  explícitamente **"por ahora"**, no de forma definitiva: queda documentada como endurecimiento futuro
  (defensa en profundidad) en las Open Questions del diseño, y el modelo no la impide — la columna
  `portal_id` y la resolución en servidor son precisamente el requisito previo para adoptarla más
  adelante si el proyecto lo justifica.
- **`portal_id` incremental (entero autonumérico) en vez de UUID.** Un id secuencial es adivinable y
  enumerable: iterar `portal_id=1, 2, 3…` en un endpoint que confía en el id del cliente expondría
  cuántos portales existen y facilitaría probar accesos cruzados por fuerza bruta. Un UUID no es
  enumerable, se genera sin coordinación central (útil al provisionar portales desde SuperAdmin sin
  depender de una secuencia de base de datos) y encaja con la respuesta 404 en accesos cruzados: ni el
  formato del id ni el código de error revelan si un portal ajeno existe.

## Consecuencias

**Positivas:** una sola base de datos que desplegar, respaldar y operar, igual que ya establece
[ADR-0001](adr-0001-postgresql-con-pgvector-como-base-de-datos-unica.md) para el motor único. El mecanismo
de aislamiento es coherente con la arquitectura de autorización ya vigente (`requiere_nivel` en servidor,
nunca en el cliente), así que no se introdujo un segundo modelo mental de seguridad para multi-tenant
además del de niveles de acceso. Es fácil de probar: el aislamiento se verifica como comportamiento de la
aplicación (intentar leer un recurso de otro portal por id directo debe dar 404) con la misma suite de
tests que ya cubre el resto de la autorización, sin depender de configurar RLS en el motor de pruebas.

**Negativas / deuda técnica:** el aislamiento depende por completo de que **toda** consulta pase por el
filtrado centralizado; olvidar aplicar `portal_id` en una consulta nueva es una fuga de datos entre
portales (IDOR) que el motor de base de datos no detendría por sí solo — a diferencia de RLS, que actúa
como defensa en profundidad incluso si una consulta de aplicación se olvida del filtro. La mitigación
vigente es disciplina de repositorio (todo acceso a datos pasa por dependencias que exigen el portal) y
una batería de pruebas de aislamiento, no una garantía del motor. Esta decisión es un trade-off aceptado
para el tamaño y alcance actuales de este proyecto, no una recomendación general: si el número de portales,
de desarrolladores tocando consultas o el nivel de riesgo aceptable cambian, RLS queda como paso siguiente
ya contemplado en el modelo (columna `portal_id` y resolución en servidor ya presentes), sin rediseño.
