import { describe, expect, it } from 'vitest'
import { aPayload, camposObligatoriosFaltantes, draftInicial, type Draft } from './articuloBorrador'
import type { ArticuloAdmin } from './admin'

function articulo(): ArticuloAdmin {
  return {
    id: 'plazos',
    categoria: 'devoluciones',
    actualizado: '2026-07-25',
    minutosLectura: 4,
    destacado: true,
    relacionados: ['reembolsos', 'envios'],
    es: {
      slug: 'plazos-de-devolucion',
      titulo: 'Plazos de devolución',
      parrafos: ['Uno.', 'Dos.'],
      howTo: { titulo: 'Cómo devolver', pasos: [{ titulo: 'Entra', descripcion: 'A tu cuenta.' }] },
      nota: 'Ojo.',
      faq: [{ pregunta: '¿Cuánto?', respuesta: '30 días.' }],
    },
    pt: {
      slug: 'prazos-de-devolucao',
      titulo: 'Prazos de devolução',
      parrafos: ['Um.', 'Dois.'],
      howTo: { titulo: 'Como devolver', pasos: [{ titulo: 'Entre', descripcion: 'Na sua conta.' }] },
      nota: null,
      faq: [{ pregunta: 'Quanto?', respuesta: '30 dias.' }],
    },
  }
}

describe('draftInicial', () => {
  it('sin artículo deja los dos idiomas en blanco', () => {
    const d = draftInicial(undefined, 'cuenta')
    expect(d.id).toBe('')
    expect(d.categoria).toBe('cuenta')
    expect(d.es.titulo).toBe('')
    expect(d.pt.titulo).toBe('')
  })

  it('sin artículo propone la fecha de hoy en ISO', () => {
    const d = draftInicial(undefined, 'cuenta')
    expect(d.actualizado).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('no comparte los arrays entre español y portugués', () => {
    // Con una constante compartida y copia superficial, `es.pasos` y `pt.pasos`
    // serían el mismo array: añadir un paso en español lo añadiría en portugués.
    const d = draftInicial(undefined, 'cuenta')
    expect(d.es.pasos).not.toBe(d.pt.pasos)
    expect(d.es.faq).not.toBe(d.pt.faq)
  })

  it('no comparte los arrays entre dos borradores distintos', () => {
    // Y tampoco entre altas sucesivas dentro de la misma sesión del panel.
    const a = draftInicial(undefined, 'cuenta')
    const b = draftInicial(undefined, 'cuenta')
    expect(a.es.pasos).not.toBe(b.es.pasos)
  })

  it('convierte los párrafos en texto de varias líneas', () => {
    // El textarea edita texto plano; la API recibe una lista.
    const d = draftInicial(articulo(), 'cuenta')
    expect(d.es.parrafos).toBe('Uno.\nDos.')
    expect(d.pt.parrafos).toBe('Um.\nDois.')
  })

  it('convierte los relacionados en una lista separada por comas', () => {
    expect(draftInicial(articulo(), 'cuenta').relacionados).toBe('reembolsos, envios')
  })

  it('muestra la nota ausente como campo vacío, no como el texto null', () => {
    const d = draftInicial(articulo(), 'cuenta')
    expect(d.es.nota).toBe('Ojo.')
    expect(d.pt.nota).toBe('')
  })

  it('copia los pasos en vez de apuntar a los del artículo cargado', () => {
    // Editar el borrador no debe alterar el objeto que devolvió la API.
    const original = articulo()
    const d = draftInicial(original, 'cuenta')
    expect(d.es.pasos[0]).not.toBe(original.es.howTo.pasos[0])
    expect(d.es.faq[0]).not.toBe(original.es.faq[0])
  })
})

describe('aPayload', () => {
  it('devuelve el artículo tal como entró, ida y vuelta', () => {
    // La conversión no puede perder ni inventar nada: es la misma que decide lo
    // que se persiste al editar.
    const original = articulo()
    expect(aPayload(draftInicial(original, 'cuenta'))).toEqual(original)
  })

  it('parte los párrafos por salto de línea y descarta los vacíos', () => {
    const d = draftInicial(undefined, 'cuenta')
    d.es.parrafos = '  Uno.  \n\n  Dos.  \n'
    expect(aPayload(d).es.parrafos).toEqual(['Uno.', 'Dos.'])
  })

  it('parte los relacionados por coma y descarta los vacíos', () => {
    const d = draftInicial(undefined, 'cuenta')
    d.relacionados = ' reembolsos , , envios ,'
    expect(aPayload(d).relacionados).toEqual(['reembolsos', 'envios'])
  })

  it('recorta los espacios del id, el slug y el título', () => {
    const d = draftInicial(undefined, 'cuenta')
    d.id = '  plazos  '
    d.es.slug = '  plazos-de-devolucion  '
    d.es.titulo = '  Plazos  '
    const p = aPayload(d)
    expect(p.id).toBe('plazos')
    expect(p.es.slug).toBe('plazos-de-devolucion')
    expect(p.es.titulo).toBe('Plazos')
  })

  it('convierte la nota en blanco a null en vez de mandar cadena vacía', () => {
    // `nota` es opcional en el contrato: la API la omite cuando es null.
    const d = draftInicial(undefined, 'cuenta')
    d.es.nota = '   '
    expect(aPayload(d).es.nota).toBeNull()
  })

  it('descarta los pasos y las preguntas que quedaron del todo vacíos', () => {
    // Las filas se añaden vacías al pulsar «añadir»; las que no se rellenan no
    // deben persistirse.
    const d = draftInicial(undefined, 'cuenta')
    d.es.pasos = [
      { titulo: 'Entra', descripcion: 'A tu cuenta.' },
      { titulo: '', descripcion: '' },
    ]
    d.es.faq = [
      { pregunta: '', respuesta: '' },
      { pregunta: '¿Cuánto?', respuesta: '30 días.' },
    ]
    const p = aPayload(d)
    expect(p.es.howTo.pasos).toHaveLength(1)
    expect(p.es.faq).toHaveLength(1)
  })

  it('conserva una fila a medio rellenar, para que el backend la valide', () => {
    // Solo se descarta lo vacío por completo: media fila es un descuido que la
    // persona debe ver, no algo que el cliente borre por su cuenta.
    const d = draftInicial(undefined, 'cuenta')
    d.es.pasos = [{ titulo: 'Entra', descripcion: '' }]
    expect(aPayload(d).es.howTo.pasos).toHaveLength(1)
  })

  it('siempre emite los dos idiomas, nunca uno solo', () => {
    // Regla del proyecto: el CRUD bilingüe es atómico.
    const p = aPayload(draftInicial(undefined, 'cuenta') as Draft)
    expect(p).toHaveProperty('es')
    expect(p).toHaveProperty('pt')
  })
})

describe('camposObligatoriosFaltantes', () => {
  const claves = (d: Draft) => camposObligatoriosFaltantes(d).map(c => c.clave)

  it('un artículo completo (ida y vuelta) no tiene campos que falten', () => {
    expect(camposObligatoriosFaltantes(draftInicial(articulo(), 'cuenta'))).toEqual([])
  })

  it('un borrador en blanco reclama id y, por cada idioma, título, slug y título del how-to', () => {
    const faltan = camposObligatoriosFaltantes(draftInicial(undefined, 'cuenta'))
    // id (1) + titulo/slug/howToTitulo por es y pt (3 × 2). La categoría llega
    // por defecto, así que no falta.
    expect(faltan).toHaveLength(7)
    expect(faltan.filter(c => c.clave === 'panelGestion.howToTitulo').map(c => c.idioma)).toEqual(['es', 'pt'])
  })

  it('exige el título del how-to: el vacío que devolvía un 500 en el contenido público', () => {
    const d = draftInicial(articulo(), 'cuenta')
    d.es.howToTitulo = '   '
    const faltan = camposObligatoriosFaltantes(d)
    expect(faltan).toEqual([{ clave: 'panelGestion.howToTitulo', idioma: 'es' }])
  })

  it('reclama el id vacío o de solo espacios', () => {
    const d = draftInicial(articulo(), 'cuenta')
    d.id = '  '
    expect(claves(d)).toContain('panelGestion.id')
  })

  it('reclama la categoría cuando no hay ninguna', () => {
    // Alta sin categorías cargadas: el select quedaría en cadena vacía.
    const d = draftInicial(undefined, '')
    expect(claves(d)).toContain('panelGestion.categoria')
  })

  it('exige el título de un paso a medio rellenar (que el backend rechazaría)', () => {
    const d = draftInicial(articulo(), 'cuenta')
    d.es.pasos = [{ titulo: '', descripcion: 'Solo descripción.' }]
    const faltan = camposObligatoriosFaltantes(d)
    expect(faltan).toEqual([{ clave: 'panelGestion.pasoTitulo', idioma: 'es', n: 1 }])
  })

  it('exige la pregunta de una FAQ a medio rellenar', () => {
    const d = draftInicial(articulo(), 'cuenta')
    d.pt.faq = [{ pregunta: '', respuesta: 'Solo respuesta.' }]
    const faltan = camposObligatoriosFaltantes(d)
    expect(faltan).toEqual([{ clave: 'panelGestion.faqPregunta', idioma: 'pt', n: 1 }])
  })

  it('no reclama filas del todo vacías: `aPayload` las descarta antes de enviar', () => {
    const d = draftInicial(articulo(), 'cuenta')
    d.es.pasos = [{ titulo: '', descripcion: '' }]
    d.es.faq = [{ pregunta: '', respuesta: '' }]
    expect(camposObligatoriosFaltantes(d)).toEqual([])
  })
})
