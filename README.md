# Centro de Ayuda

Un **Centro de Ayuda** multi-tenant para atención al cliente, en español y portugués.

## Propósito

Reducir la carga de soporte dando a las personas usuarias respuestas correctas por sí mismas, y convertir
lo que el centro no sabe responder en contenido nuevo. El producto se apoya en tres piezas:

- **Base de conocimiento** — artículos organizados por categorías, con buscador protagonista y contacto con
  soporte como último recurso.
- **Chatbot con citas** — responde a partir de la base de conocimiento y muestra las fuentes de cada
  respuesta; cuando no encuentra la información, lo dice y escala a soporte en lugar de inventar.
- **Panel interno de preguntas sin resolver** — siguiendo el ciclo KCS, toda pregunta sin respuesta queda
  registrada como candidata a convertirse en artículo.

La accesibilidad es un requisito del producto, no un extra: el centro debe cumplir **WCAG 2.2 nivel AA**.

## Estado actual

**Prototipo funcional** de las 4 pantallas, navegable en local y con datos ficticios. El chatbot es
interfaz: muestra una conversación de ejemplo con citas, pero no hay capa RAG.

El **backend** (FastAPI + PostgreSQL/pgvector) está implementado en `api/`: artículos administrables desde
el Panel Interno tras un login de administrador, con el RAG dejado preparado para el futuro. Los pasos para
arrancarlo (configuración inicial y arranque diario) están en **`api/README.md`**.

Qué funciona: buscador con filtrado real, acordeón de preguntas frecuentes, valoración de artículos, tabla
del panel interno con filtros, chat con citas que enlazan a artículos existentes, y todo el contenido en
español y portugués con el idioma en la dirección (`/es/…`, `/pt/…`).

El repositorio contiene además:

- `docs/architecture/` — diagramas C4 del sistema:
  [contexto](docs/architecture/c4-level1-context.md) (quién usa el sistema y de qué depende) y
  [contenedores](docs/architecture/c4-level2-container.md) (qué piezas lo forman, con qué tecnología
  y por qué), y los ADR de las decisiones de arquitectura.

Ver `AGENTS.md` (versión neutra, válida para cualquier agente de código) y `CLAUDE.md` (mismo contenido para
Claude Code) para el stack, los comandos y las convenciones vigentes.
