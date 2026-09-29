---
name: crear-pr
description: Integra los cambios pendientes mediante un Pull Request. Úsalo cuando haya trabajo listo para subir, cuando se pida "hacer un commit", "subir esto" o "abrir un PR". Es la única vía permitida por CLAUDE.md para integrar cambios en este repositorio.
compatibility: Requiere git y la CLI de GitHub (gh) autenticada.
metadata:
  author: jorgeelopezm
  version: "1.0"
---

Prepara y abre un Pull Request con el trabajo pendiente.

`CLAUDE.md` prohíbe el commit directo: todo se integra por PR y a través de este skill. También exige que
cualquier comando lo apruebe la persona desarrolladora, así que **este procedimiento reúne todo lo que va a
pasar, lo enseña en un único bloque de revisión y no toca nada hasta recibir el visto bueno.**

---

## Convenciones del repositorio

- Rama: kebab-case en español, **sin prefijo de tipo** (`prototipo-centro-ayuda`, no `feat/...`).
- Commit: asunto en imperativo y en español, sin prefijo `feat:`/`docs:`. Cuerpo explicando el porqué.
- PR: título y cuerpo en español.
- Base siempre `main`.

## Pasos

### 1. Comprobaciones previas

```bash
git rev-parse --is-inside-work-tree
git fetch origin
gh auth status
```

- Si no es un repositorio git, detente y dilo.
- `git fetch` evita ramificar sobre información desactualizada.
- **Fíjate en qué cuenta de GitHub está activa.** Esta máquina tiene más de una en el llavero y el remoto
  es un repositorio de organización: abrir el PR con la identidad equivocada es un fallo silencioso y
  engorroso de revertir. Si la cuenta activa no encaja con el remoto, avísalo antes de seguir.
- Si `gh` no está autenticado, **no intentes autenticarlo tú**: es un flujo interactivo. Pide a la persona
  que ejecute `gh auth login`, sugiriéndole el prefijo `!` para lanzarlo desde la propia sesión.

### 2. Determinar qué entra

```bash
git status --short
git diff
git diff --staged
```

Si no hay nada que confirmar, detente y dilo: no crees ramas ni PR vacíos.

Revisa la lista y descarta lo que no deba viajar: volcados locales (p. ej. salida de tests),
archivos de compilación, y cualquier cosa con aspecto de credencial, token o `.env`. Si dudas sobre si
algo entra o no, **pregunta** en lugar de decidir por tu cuenta: `CLAUDE.md` obliga a entrar en modo
entrevista ante la ambigüedad.

### 3. Elegir la rama

```bash
git branch --show-current
```

- Para la rama usa un nombre corto en español de lo que hace el cambio.
- **Si estás en `main`, hay que crear rama.** Nunca confirmes ni subas nada sobre `main`.
- Comprueba si la rama ya existe en local o en el remoto:

```bash
git rev-parse --verify <rama> 2>/dev/null
gh pr list --head <rama> --json number,url,title
```

Si ya hay un PR abierto para esa rama, ofrece **añadir el commit al PR existente** en vez de abrir otro.

### 4. Redactar el commit

Asunto en imperativo, en español, sin prefijo de tipo. Cuerpo explicando por qué, no qué (el diff ya dice
qué). Cierra siempre con el trailer de atribución:

```
Añade las reglas de trabajo y el cambio del prototipo

Deja por escrito el flujo de aprobación y de PR, y versiona las
decisiones de stack que hasta ahora vivían fuera del repositorio.

```

### 5. Redactar el PR

Título en español, sin prefijo. Cuerpo con tres bloques: qué cambia, por qué, y cómo verificarlo. Termina
con la nota de generación:

```markdown
## Qué cambia
<!-- lista breve -->

## Por qué
<!-- el problema que resuelve -->

## Cómo verificarlo
<!-- pasos concretos para comprobarlo -->

```

### 6. Presentar el bloque de revisión

Muestra el conjunto y **espera aprobación explícita**. No ejecutes nada todavía:

```
Rama:    prototipo-centro-ayuda
Cuenta:  jorgeelopezm (activa)
Incluye: CLAUDE.md, .gitignore, .claude/
Commit:  Añade las reglas de trabajo y el cambio del prototipo
PR:      "Reglas de trabajo y cambio especificaciones del prototipo"
         base: main  <-  prototipo-centro-ayuda

¿Ejecuto? [aprobar / editar / cancelar]
```

- `aprobar` → continúa al paso 7.
- `editar` → ajusta lo que se pida y vuelve a mostrar el bloque.
- `cancelar` → no hagas nada. El árbol de trabajo queda como estaba.

### 7. Ejecutar

Solo después de la aprobación:

```bash
git checkout -b <rama>
git add <rutas explícitas>
git commit -m "<mensaje>"
git push -u origin <rama>
gh pr create --base main --title "<título>" --body "<cuerpo>"
```

Usa un heredoc para los textos de varias líneas, de modo que los saltos de línea sobrevivan.

### 8. Informar

Devuelve la URL del PR y recuerda que la rama local quedó activa. Si algún paso falla, di exactamente cuál
y en qué estado quedó el repositorio: no lo dejes a medias sin avisar.

---

## Salvaguardas

- **Nunca** hagas commit ni push sobre `main`.
- **Nunca** uses `--force`, `--no-verify` ni `--no-gpg-sign`. Si un hook falla, investiga la causa.
- **Nunca** uses `git add -A` ni `git add .`: rutas explícitas, las mismas que se aprobaron en el bloque
  de revisión.
- **Nunca** fusiones el PR ni lo cierres. Eso lo decide la persona desarrolladora.
- No ejecutes comandos interactivos (`gh auth login`, `git rebase -i`): pídelos.
- Ante ambigüedad sobre el alcance, la rama o el mensaje, pregunta antes de avanzar.
