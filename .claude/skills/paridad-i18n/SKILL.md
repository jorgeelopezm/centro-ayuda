---
name: paridad-i18n
description: Verifica que las etiquetas de interfaz y el contenido de datos existan y coincidan en español y portugués, tipados contra el contrato de datos. Detecta claves huérfanas e ítems que existen en un idioma y no en el otro. Úsalo tras añadir o editar textos o contenido, o cuando se pida "revisa es/pt" o "faltan traducciones".
compatibility: Solo lectura y análisis. No rellena traducciones ni edita archivos por su cuenta.
metadata:
  author: jorgeelopezm
  version: "1.0"
---

Comprueba la paridad español/portugués de la aplicación.

`CLAUDE.md` fija **español y portugués desde el inicio**: todo texto de interfaz y todo contenido debe
existir en ambos. El modo más común de romperlo es añadir algo en un solo idioma. Este skill hace visible
esa deriva y **reporta las diferencias**; no inventa traducciones ni edita por su cuenta.

---

## Dos capas que revisar

La app tiene dos fuentes de texto paralelas, cada una con su versión es y pt:

1. **Etiquetas de interfaz (i18next).** JSON en `app/src/i18n/locales/es/ui.json` y
   `app/src/i18n/locales/pt/ui.json`. Registradas en `app/src/i18n/config.ts` bajo el namespace `ui`.
2. **Contenido de datos.** Módulos tipados en `app/src/data/es/` y `app/src/data/pt/`
   (`categorias`, `articulos`, `conversacion`, `preguntas-sin-resolver`), unidos en
   `app/src/data/index.ts` y descritos por `app/src/types.ts` (`ContenidoIdioma`).

## Comprobaciones

### 1. Claves de interfaz (ui.json)

Compara la estructura de claves de `es/ui.json` y `pt/ui.json`, **de forma recursiva**:

- Claves presentes en un idioma y ausentes en el otro → **hallazgo**.
- Claves cuyo valor sigue en el idioma de origen (p. ej. texto español dentro de `pt/ui.json`) → **posible
  traducción pendiente**; márcalo, no lo corrijas.
- Diferencias de forma (una clave es objeto en un idioma y cadena en el otro) → **hallazgo**.

### 2. Paridad de contenido (data)

Para cada colección de `ContenidoIdioma`, contrasta es contra pt usando el identificador **estable entre
idiomas**, no el `slug` (que es propio de cada idioma):

- **Categorías:** el conjunto de `id` (`IdCategoria`) debe ser idéntico en ambos idiomas.
- **Artículos:** el conjunto de `id` debe coincidir. Además, cada `id` referenciado en `relacionados`,
  en las citas de `conversacion` (`Cita.articuloId`) y en los fragmentos de cita debe resolver a un
  artículo **que exista en ese idioma**.
- **Preguntas sin resolver** y **métricas:** deben existir en ambos idiomas; las `clave` de `Metrica`
  (`sinResolver`/`conCita`/`creados`) deben coincidir.
- Señala también artículos cuyos campos de texto (`titulo`, `parrafos`, `faq`) sigan en español dentro de
  la carpeta `pt/` (traducción pendiente).

### 3. Coherencia con el contrato

Cualquier ítem debe seguir cumpliendo `types.ts`. Un campo que exista en un idioma con una forma y en el
otro con otra es un hallazgo aunque ambos "existan".

## Informe

Agrupa por capa y entrega diferencias concretas:

```
Interfaz (ui.json)
  - falta en pt: home.subtitulo
  - sin traducir en pt: chat.aviso (= valor español)

Contenido (data)
  - artículo id "reembolsos" existe en es, falta en pt
  - cita articuloId "seguridad-2fa" en pt/conversacion no resuelve a ningún artículo pt
```

Cierra con un recuento por capa. Si todo cuadra, dilo y resume qué se comparó.

## Salvaguardas

- **No rellenes traducciones inventadas** ni edites archivos: este skill detecta e informa. Las
  traducciones las aporta o aprueba la persona desarrolladora y se integran por `crear-pr`.
- Compara por identificador estable (`id`, `clave`), nunca por `slug` ni por dirección: son propios de
  cada idioma por diseño y no deben coincidir.
- Ante ambigüedad sobre si una diferencia es intencionada, pregunta antes de darla por error.
