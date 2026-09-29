/**
 * Conversión entre el borrador que edita el formulario y el `ArticuloAdmin` que
 * viaja a la API.
 *
 * El borrador guarda como texto plano lo que la API recibe como listas
 * (párrafos separados por saltos de línea, relacionados separados por comas):
 * esa traducción de ida y vuelta es lógica pura y vive fuera del componente.
 * El artículo siempre lleva los dos idiomas, nunca uno solo.
 */

import { IDIOMAS, type Idioma } from '@/types'
import type { ArticuloAdmin, TraduccionAdmin } from '@/data/admin'

export type TradDraft = {
  slug: string
  titulo: string
  parrafos: string
  nota: string
  howToTitulo: string
  pasos: { titulo: string; descripcion: string }[]
  faq: { pregunta: string; respuesta: string }[]
}
export type Draft = {
  id: string
  categoria: string
  actualizado: string
  minutosLectura: number
  destacado: boolean
  relacionados: string
  es: TradDraft
  pt: TradDraft
}

/**
 * Traducción en blanco. Es una función y no una constante compartida a
 * propósito: con `{ ...tradVacia }` los arrays `pasos` y `faq` no se copian, así
 * que español y portugués acabarían apuntando al mismo array (y al del módulo).
 * Hoy nadie los muta —el formulario siempre reemplaza— pero un `push` futuro
 * escribiría el paso en los dos idiomas a la vez.
 */
const tradVacia = (): TradDraft => ({
  slug: '', titulo: '', parrafos: '', nota: '', howToTitulo: '', pasos: [], faq: [],
})

export function draftInicial(inicial: ArticuloAdmin | undefined, categoriaPorDefecto: string): Draft {
  if (!inicial) {
    return {
      id: '', categoria: categoriaPorDefecto, actualizado: new Date().toISOString().slice(0, 10),
      minutosLectura: 3, destacado: false, relacionados: '', es: tradVacia(), pt: tradVacia(),
    }
  }
  const trad = (t: TraduccionAdmin): TradDraft => ({
    slug: t.slug, titulo: t.titulo, parrafos: t.parrafos.join('\n'), nota: t.nota ?? '',
    howToTitulo: t.howTo.titulo, pasos: t.howTo.pasos.map(p => ({ ...p })), faq: t.faq.map(f => ({ ...f })),
  })
  return {
    id: inicial.id, categoria: inicial.categoria, actualizado: inicial.actualizado,
    minutosLectura: inicial.minutosLectura, destacado: inicial.destacado,
    relacionados: inicial.relacionados.join(', '), es: trad(inicial.es), pt: trad(inicial.pt),
  }
}

function tradPayload(t: TradDraft): TraduccionAdmin {
  return {
    slug: t.slug.trim(),
    titulo: t.titulo.trim(),
    parrafos: t.parrafos.split('\n').map(s => s.trim()).filter(Boolean),
    howTo: { titulo: t.howToTitulo.trim(), pasos: t.pasos.filter(p => p.titulo.trim() || p.descripcion.trim()) },
    nota: t.nota.trim() || null,
    faq: t.faq.filter(f => f.pregunta.trim() || f.respuesta.trim()),
  }
}

export function aPayload(d: Draft): ArticuloAdmin {
  return {
    id: d.id.trim(), categoria: d.categoria, actualizado: d.actualizado,
    minutosLectura: d.minutosLectura, destacado: d.destacado,
    relacionados: d.relacionados.split(',').map(s => s.trim()).filter(Boolean),
    es: tradPayload(d.es), pt: tradPayload(d.pt),
  }
}

/**
 * Un campo obligatorio que falta. `clave` es la clave i18n de su etiqueta;
 * `idioma` acota el aviso al idioma afectado (los campos por idioma van dos
 * veces, es y pt); `n` numera la fila en pasos/FAQ.
 */
export type CampoFaltante = { clave: string; idioma?: Idioma; n?: number }

/**
 * Candado de guardado: enumera los campos obligatorios que faltan en el
 * borrador, con las MISMAS reglas que el backend acepta (ver `schemas.py`:
 * `TraduccionArticuloIn`/`BloqueHowTo`). Así el formulario nunca envía un
 * artículo que la API vaya a rechazar (422) ni que, ya persistido, rompa el
 * contenido público al serializarse (un `howTo.titulo` vacío devolvía un 500).
 *
 * Es lógica pura y espeja el recorte de `aPayload`: valida sobre el texto ya
 * sin espacios, para que un valor de solo espacios cuente como ausente. Si
 * devuelve una lista vacía, el borrador cumple los mínimos del backend.
 */
export function camposObligatoriosFaltantes(d: Draft): CampoFaltante[] {
  const faltan: CampoFaltante[] = []
  if (!d.id.trim()) faltan.push({ clave: 'panelGestion.id' })
  if (!d.categoria.trim()) faltan.push({ clave: 'panelGestion.categoria' })

  for (const idioma of IDIOMAS) {
    const t = d[idioma]
    if (!t.titulo.trim()) faltan.push({ clave: 'panelGestion.tituloArticulo', idioma })
    if (!t.slug.trim()) faltan.push({ clave: 'panelGestion.slug', idioma })
    if (!t.howToTitulo.trim()) faltan.push({ clave: 'panelGestion.howToTitulo', idioma })

    // `aPayload` conserva un paso/FAQ si tiene título O descripción; el backend
    // exige el título/pregunta. Se avisa solo de las filas que llegarían a la API.
    t.pasos.forEach((p, i) => {
      if ((p.titulo.trim() || p.descripcion.trim()) && !p.titulo.trim())
        faltan.push({ clave: 'panelGestion.pasoTitulo', idioma, n: i + 1 })
    })
    t.faq.forEach((f, i) => {
      if ((f.pregunta.trim() || f.respuesta.trim()) && !f.pregunta.trim())
        faltan.push({ clave: 'panelGestion.faqPregunta', idioma, n: i + 1 })
    })
  }
  return faltan
}
