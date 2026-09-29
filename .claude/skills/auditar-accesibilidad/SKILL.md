---
name: auditar-accesibilidad
description: Audita los cambios de interfaz contra WCAG 2.2 nivel AA (contraste, foco, objetivos táctiles, etiquetas, teclado, estados sin color) y reporta los hallazgos ordenados por severidad con el arreglo concreto. Úsalo tras tocar cualquier componente o página, o cuando se pida "revisa accesibilidad" o "¿esto cumple WCAG?".
compatibility: Solo lectura y análisis. No edita archivos ni ejecuta comandos por su cuenta.
metadata:
  author: jorgeelopezm
  version: "1.0"
---

Revisa la accesibilidad de los cambios pendientes contra WCAG 2.2 nivel AA.

`CLAUDE.md` declara la accesibilidad AA como **requisito no negociable**, no como mejora posterior. Este
skill la convierte en una puerta repetible: recorre lo que cambió, lo contrasta contra una checklist fija
y **reporta**; no edita ni arregla por su cuenta (eso lo aprueba la persona desarrolladora). La fuente de
la verdad de los requisitos es la convención de accesibilidad de `CLAUDE.md` (WCAG 2.2 nivel AA).

---

## Alcance

Por defecto, solo los archivos con cambios sin confirmar. Si no hay cambios, pregunta si se audita todo
`app/src/components/` y `app/src/pages/` o una pantalla concreta.

Para ver qué cambió (solo lectura):

```bash
git status --short
git diff
```

## Checklist WCAG 2.2 AA

Para cada componente o página tocada, comprueba cada punto y anota si **cumple**, **falla** o **no aplica**:

1. **Contraste.** Texto normal ≥ 4.5:1; texto grande y componentes de interfaz ≥ 3:1. El color de acento
   se lee del token `--acento`; verifica el contraste sobre su fondo real, no sobre blanco por defecto.
   Ojo con las clases de color de las tarjetas de categoría (`fondo`/`texto` en `Categoria`).
2. **Foco visible.** Todo elemento interactivo tiene un estado de foco propio (anillo de 2px con contraste
   suficiente), **distinto del hover** y nunca eliminado con `outline: none` sin sustituto.
3. **Objetivos táctiles.** Controles principales de al menos 44×44px, incluido el botón flotante de chat.
4. **Etiquetas visibles.** Todo campo tiene etiqueta visible (no solo `placeholder`). Los errores de
   formulario se comunican con **texto e icono, no solo con color**.
5. **Nada solo por color.** Ningún estado (chip KCS `nueva`/`revision`/`cubierta`, disponibilidad, error)
   depende únicamente del color: debe haber texto, forma o icono que lo acompañe.
6. **Teclado.** Todo es operable por teclado, en orden lógico. Sin trampas de foco. Al abrir el panel del
   chat, el foco pasa a él; al cerrarlo, vuelve al disparador.
7. **Lectores de pantalla.** Mensajes nuevos del asistente anunciados con `aria-live`. Iconos con texto
   alternativo o `aria-hidden` si son decorativos. Jerarquía de encabezados lógica (un solo `h1` por
   pantalla, sin saltos de nivel).
8. **"Saltar al contenido".** El enlace de salto (`SkipLink`) es visible al recibir foco.
9. **Movimiento.** Sin animaciones imprescindibles; se respeta `prefers-reduced-motion`.
10. **Idiomas.** El atributo `lang` acompaña al idioma activo (es/pt) y los textos alternativos y etiquetas
    accesibles existen en ambos idiomas (esto se cruza con el skill `paridad-i18n`).

## Componentes de referencia ya resueltos

Úsalos como patrón de lo que sí cumple, no como sospechosos por defecto: `SkipLink.tsx`, `ChatWidget.tsx`,
`SelectorIdioma.tsx`, `A11yAnnotationPanel.tsx`, `KcsChip.tsx`, `EscalationBlock.tsx`.

## Informe

Entrega los hallazgos **ordenados de más grave a menos**, cada uno con:

```
[severidad] archivo:línea — criterio WCAG afectado
Qué pasa: <descripción del problema>
Arreglo: <cambio concreto sugerido>
```

- Severidad **alta**: bloquea el uso con teclado o lector, o incumple un mínimo (contraste, 44×44px).
- Severidad **media**: degrada la experiencia pero hay alternativa.
- Severidad **baja**: pulido o buena práctica.

Cierra con un recuento (`N altas, M medias, K bajas`). Si no hay hallazgos, dilo con claridad y lista qué
archivos se auditaron.

## Salvaguardas

- **No edites ni "arregles" por tu cuenta.** Este skill audita e informa; los cambios los aprueba la
  persona desarrolladora y se integran por `crear-pr`.
- No inventes números de contraste: si no puedes calcularlo con certeza (p. ej. depende de un token en
  tiempo de ejecución), decláralo como "revisar manualmente" en lugar de afirmar un ratio.
- Ante ambigüedad sobre el alcance de la auditoría, pregunta antes de avanzar.
