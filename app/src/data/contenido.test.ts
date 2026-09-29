import { describe, expect, it } from 'vitest'
import {
  IDIOMAS,
  type ContenidoIdioma,
  type EstadoKcs,
  type Idioma,
  type MensajeChat,
  type PreguntaSinResolver,
} from '@/types'
import { articulos as articulosEs } from './es/articulos'
import { categorias as categoriasEs } from './es/categorias'
import { conversacion as conversacionEs } from './es/conversacion'
import { metricas as metricasEs, preguntasSinResolver as preguntasEs } from './es/preguntas-sin-resolver'
import { articulos as articulosPt } from './pt/articulos'
import { categorias as categoriasPt } from './pt/categorias'
import { conversacion as conversacionPt } from './pt/conversacion'
import { metricas as metricasPt, preguntasSinResolver as preguntasPt } from './pt/preguntas-sin-resolver'
import { articuloPorId, articuloPorSlug, articulosDestacados, buscarArticulos, contarPorCategoria } from './index'

/**
 * Integridad del contenido estático de `src/data/{es,pt}`.
 *
 * Estos módulos alimentan el seed del backend (`scripts/exportar-datos.mjs`), así
 * que un enlace roto o un artículo que solo existe en un idioma se propaga a la
 * API. Las comprobaciones son invariantes del contenido, no del texto concreto:
 * añadir o traducir artículos no rompe estos tests; olvidarse de un idioma sí.
 *
 * **Alcance por portal (multi-tenant).** Tras el cambio a multi-tenant este contenido
 * estático es el **seed del portal `default`**: la paridad es/pt es un invariante *por
 * portal*, y aquí se comprueba la del `default`. La paridad de los demás portales —que
 * se pueblan por el panel, no por este seed— la garantiza en el servidor el CRUD
 * bilingüe atómico (crear/editar exige es+pt juntos; ningún artículo persiste en un solo
 * idioma), probado en `api/tests/test_admin_articulos.py` y, por portal aislado, en
 * `api/tests/test_aislamiento.py`.
 */

const contenidos: Record<Idioma, ContenidoIdioma> = {
  es: { empresa: '[Empresa]', acento: '#4338ca', bannerDesde: '#3730a3', bannerMedio: '#4338ca', bannerHasta: '#4f46e5', plantilla: 'default', logo: false, logoVersion: null, categorias: categoriasEs, articulos: articulosEs, conversacion: conversacionEs, metricas: metricasEs },
  pt: { empresa: '[Empresa]', acento: '#4338ca', bannerDesde: '#3730a3', bannerMedio: '#4338ca', bannerHasta: '#4f46e5', plantilla: 'default', logo: false, logoVersion: null, categorias: categoriasPt, articulos: articulosPt, conversacion: conversacionPt, metricas: metricasPt },
}

const preguntasPorIdioma: Record<Idioma, PreguntaSinResolver[]> = { es: preguntasEs, pt: preguntasPt }

const ESTADOS_KCS: EstadoKcs[] = ['nueva', 'revision', 'cubierta']

/** Segmento de dirección: minúsculas, dígitos y guiones simples. */
const FORMATO_SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

/** Fecha ISO completa y real: descarta `2026-02-31`, que `Date.parse` sí acepta. */
function esFechaIso(valor: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(valor)) return false
  const fecha = new Date(`${valor}T00:00:00Z`)
  return !Number.isNaN(fecha.getTime()) && fecha.toISOString().slice(0, 10) === valor
}

type MensajeCitado = Extract<MensajeChat, { clase: 'citado' }>

function mensajesCitados(conversacion: MensajeChat[]): MensajeCitado[] {
  return conversacion.filter(
    (mensaje): mensaje is MensajeCitado => mensaje.autor === 'asistente' && mensaje.clase === 'citado',
  )
}

function duplicados(valores: string[]): string[] {
  return valores.filter((valor, indice) => valores.indexOf(valor) !== indice)
}

// --- Invariantes de cada idioma ---------------------------------------------

describe.each([...IDIOMAS])('contenido de %s', idioma => {
  const contenido = contenidos[idioma]
  const { articulos, categorias, conversacion, metricas } = contenido
  const preguntas = preguntasPorIdioma[idioma]

  it('publica artículos y categorías', () => {
    expect(articulos.length).toBeGreaterThan(0)
    expect(categorias.length).toBeGreaterThan(0)
  })

  it('no repite identificadores de categoría', () => {
    expect(duplicados(categorias.map(c => c.id))).toEqual([])
  })

  it('no repite slugs de categoría dentro del idioma', () => {
    expect(duplicados(categorias.map(c => c.slug))).toEqual([])
  })

  it('asigna a cada artículo una categoría declarada', () => {
    const declaradas = new Set(categorias.map(c => c.id))
    const huerfanos = articulos.filter(a => !declaradas.has(a.categoria)).map(a => a.id)
    expect(huerfanos).toEqual([])
  })

  it('no repite identificadores de artículo', () => {
    expect(duplicados(articulos.map(a => a.id))).toEqual([])
  })

  it('no repite slugs de artículo: un slug duplicado dejaría un artículo inalcanzable', () => {
    expect(duplicados(articulos.map(a => a.slug))).toEqual([])
  })

  it('usa slugs con forma de segmento de dirección', () => {
    const invalidos = articulos.filter(a => !FORMATO_SLUG.test(a.slug)).map(a => a.slug)
    expect(invalidos).toEqual([])
  })

  it('usa identificadores estables con forma de segmento de dirección', () => {
    const invalidos = articulos.filter(a => !FORMATO_SLUG.test(a.id)).map(a => a.id)
    expect(invalidos).toEqual([])
  })

  it('resuelve por slug todos los artículos publicados', () => {
    const sinResolver = articulos.filter(a => articuloPorSlug(contenido, a.slug)?.id !== a.id).map(a => a.slug)
    expect(sinResolver).toEqual([])
  })

  it('resuelve por identificador todos los artículos publicados', () => {
    const sinResolver = articulos.filter(a => articuloPorId(contenido, a.id)?.id !== a.id).map(a => a.id)
    expect(sinResolver).toEqual([])
  })

  it('enlaza solo artículos relacionados que existen', () => {
    const existentes = new Set(articulos.map(a => a.id))
    const rotos = articulos.flatMap(a => a.relacionados.filter(r => !existentes.has(r)).map(r => `${a.id} → ${r}`))
    expect(rotos).toEqual([])
  })

  it('no relaciona un artículo consigo mismo', () => {
    const autorreferencias = articulos.filter(a => a.relacionados.includes(a.id)).map(a => a.id)
    expect(autorreferencias).toEqual([])
  })

  it('fecha cada artículo con una fecha ISO válida para el atributo datetime', () => {
    const invalidas = articulos.filter(a => !esFechaIso(a.actualizado)).map(a => `${a.id}: ${a.actualizado}`)
    expect(invalidas).toEqual([])
  })

  it('declara un tiempo de lectura positivo', () => {
    const invalidos = articulos.filter(a => !Number.isInteger(a.minutosLectura) || a.minutosLectura <= 0)
    expect(invalidos.map(a => a.id)).toEqual([])
  })

  it('trae el contenido mínimo que renderiza la pantalla de artículo', () => {
    const incompletos = articulos
      .filter(
        a =>
          a.titulo.trim() === '' ||
          a.parrafos.length === 0 ||
          a.parrafos.some(p => p.trim() === '') ||
          a.howTo.titulo.trim() === '' ||
          a.howTo.pasos.length === 0 ||
          a.faq.length === 0,
      )
      .map(a => a.id)
    expect(incompletos).toEqual([])
  })

  it('describe cada paso del bloque how-to con título y descripción', () => {
    const incompletos = articulos
      .filter(a => a.howTo.pasos.some(p => p.titulo.trim() === '' || p.descripcion.trim() === ''))
      .map(a => a.id)
    expect(incompletos).toEqual([])
  })

  it('responde cada pregunta frecuente', () => {
    const incompletas = articulos
      .filter(a => a.faq.some(f => f.pregunta.trim() === '' || f.respuesta.trim() === ''))
      .map(a => a.id)
    expect(incompletas).toEqual([])
  })

  it('destaca artículos para la portada', () => {
    expect(articulosDestacados(contenido).length).toBeGreaterThan(0)
  })

  it('reparte todos los artículos al contar por categoría', () => {
    const total = Object.values(contarPorCategoria(articulos)).reduce((suma, n) => suma + n, 0)
    expect(total).toBe(articulos.length)
  })

  it('encuentra por el nombre de categoría del idioma al menos los artículos de esa categoría', () => {
    for (const categoria of categorias) {
      const esperados = articulos.filter(a => a.categoria === categoria.id).map(a => a.id)
      const encontrados = buscarArticulos(contenido, categoria.nombre).map(a => a.id)
      expect(encontrados).toEqual(expect.arrayContaining(esperados))
    }
  })

  it('cita en el chat solo artículos que existen', () => {
    const citas = mensajesCitados(conversacion).flatMap(m => m.citas)
    expect(citas.length).toBeGreaterThan(0)
    const rotas = citas.filter(c => articuloPorId(contenido, c.articuloId) === undefined).map(c => c.articuloId)
    expect(rotas).toEqual([])
  })

  it('titula cada cita como el artículo citado', () => {
    const citas = mensajesCitados(conversacion).flatMap(m => m.citas)
    const desajustadas = citas
      .filter(c => articuloPorId(contenido, c.articuloId)?.titulo !== c.titulo)
      .map(c => c.articuloId)
    expect(desajustadas).toEqual([])
  })

  it('numera cada marca de cita del texto con una fuente de la lista', () => {
    for (const mensaje of mensajesCitados(conversacion)) {
      const marcas = mensaje.fragmentos.filter(f => f.tipo === 'cita').map(f => f.n)
      const fuentes = mensaje.citas.map(c => c.n)
      expect(marcas.length).toBeGreaterThan(0)
      expect([...new Set(marcas)].sort()).toEqual([...fuentes].sort())
    }
  })

  it('no repite el número de fuente dentro de un mensaje', () => {
    for (const mensaje of mensajesCitados(conversacion)) {
      expect(duplicados(mensaje.citas.map(c => String(c.n)))).toEqual([])
    }
  })

  it('demuestra en la conversación de ejemplo el saludo, la respuesta con citas y el caso sin resultado', () => {
    const clases = conversacion.filter(m => m.autor === 'asistente').map(m => m.clase)
    expect(clases).toContain('saludo')
    expect(clases).toContain('citado')
    // El caso sin resultado es el que deriva a una persona: no puede desaparecer.
    expect(clases).toContain('sin-resultado')
  })

  it('mantiene la similitud de las preguntas sin resolver entre 0 y 1', () => {
    const fuera = preguntas.filter(p => p.similitud < 0 || p.similitud > 1).map(p => p.pregunta)
    expect(fuera).toEqual([])
  })

  it('cuenta al menos una vez cada pregunta sin resolver', () => {
    const invalidas = preguntas.filter(p => !Number.isInteger(p.veces) || p.veces < 1).map(p => p.pregunta)
    expect(invalidas).toEqual([])
  })

  it('fecha las preguntas sin resolver con fechas ISO válidas', () => {
    const invalidas = preguntas.filter(p => !esFechaIso(p.fecha)).map(p => p.fecha)
    expect(invalidas).toEqual([])
  })

  it('usa solo estados del ciclo KCS', () => {
    const desconocidos = preguntas.filter(p => !ESTADOS_KCS.includes(p.estado)).map(p => p.estado)
    expect(desconocidos).toEqual([])
  })

  it('declara las tres métricas del panel sin repetir clave', () => {
    expect(metricas.map(m => m.clave)).toEqual(['sinResolver', 'conCita', 'creados'])
    expect(metricas.every(m => m.valor.trim() !== '')).toBe(true)
  })
})

// --- Paridad entre idiomas --------------------------------------------------

// Paridad es/pt **del portal `default`** (este seed). Para los demás portales el mismo
// invariante lo impone el CRUD bilingüe atómico del backend, no este fichero.
describe('paridad es/pt (portal default)', () => {
  const es = contenidos.es
  const pt = contenidos.pt

  it('publica los mismos artículos, en el mismo orden', () => {
    // El identificador es estable entre idiomas: cambiar de idioma no pierde el artículo.
    expect(pt.articulos.map(a => a.id)).toEqual(es.articulos.map(a => a.id))
  })

  it('clasifica cada artículo en la misma categoría en ambos idiomas', () => {
    expect(pt.articulos.map(a => a.categoria)).toEqual(es.articulos.map(a => a.categoria))
  })

  it('fecha cada artículo igual en ambos idiomas', () => {
    expect(pt.articulos.map(a => a.actualizado)).toEqual(es.articulos.map(a => a.actualizado))
  })

  it('destaca los mismos artículos en ambos idiomas', () => {
    expect(articulosDestacados(pt).map(a => a.id)).toEqual(articulosDestacados(es).map(a => a.id))
  })

  it('mantiene la misma red de artículos relacionados', () => {
    expect(pt.articulos.map(a => a.relacionados)).toEqual(es.articulos.map(a => a.relacionados))
  })

  it('traduce la nota opcional en los dos idiomas o en ninguno', () => {
    const desajustes = es.articulos
      .filter((articulo, i) => (articulo.nota !== undefined) !== (pt.articulos[i].nota !== undefined))
      .map(a => a.id)
    expect(desajustes).toEqual([])
  })

  it('traduce todos los párrafos, pasos y preguntas frecuentes', () => {
    const forma = (contenido: ContenidoIdioma) =>
      contenido.articulos.map(a => [a.parrafos.length, a.howTo.pasos.length, a.faq.length])
    expect(forma(pt)).toEqual(forma(es))
  })

  it('declara las mismas categorías con el mismo icono', () => {
    // El icono es presentación, no idioma: debe coincidir. El color ya no es un
    // atributo de la categoría (se deriva del acento del portal).
    const presentacion = (contenido: ContenidoIdioma) => contenido.categorias.map(c => [c.id, c.icono])
    expect(presentacion(pt)).toEqual(presentacion(es))
  })

  it('traduce el nombre visible de cada categoría sin dejarlo vacío', () => {
    expect(pt.categorias.every(c => c.nombre.trim() !== '')).toBe(true)
    expect(es.categorias.every(c => c.nombre.trim() !== '')).toBe(true)
  })

  it('cita los mismos artículos en la conversación de ambos idiomas', () => {
    const citados = (contenido: ContenidoIdioma) =>
      mensajesCitados(contenido.conversacion).flatMap(m => m.citas.map(c => c.articuloId))
    expect(citados(pt)).toEqual(citados(es))
  })

  it('mantiene la misma cola de preguntas sin resolver', () => {
    // Es la misma cola traducida: cambian los textos, no las cifras ni el estado.
    const metadatos = (preguntas: PreguntaSinResolver[]) =>
      preguntas.map(p => [p.veces, p.similitud, p.fecha, p.estado])
    expect(metadatos(preguntasPt)).toEqual(metadatos(preguntasEs))
  })

  it('declara las mismas métricas del panel', () => {
    expect(pt.metricas.map(m => m.clave)).toEqual(es.metricas.map(m => m.clave))
  })
})
