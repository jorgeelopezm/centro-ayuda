import { afterEach, describe, expect, it, vi } from 'vitest'
import { IDIOMAS, esIdioma } from '@/types'
import { detectarIdioma, recursos } from './config'

/**
 * `detectarIdioma` solo lee `navigator`, así que se sustituye por un doble: los
 * tests corren en entorno `node` y no hay navegador que preguntar.
 */
function stubNavegador(preferencias: { languages?: string[]; language?: string }): void {
  vi.stubGlobal('navigator', preferencias)
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('detectarIdioma', () => {
  it('elige portugués si es el idioma preferido', () => {
    stubNavegador({ languages: ['pt-BR', 'en-US'] })
    expect(detectarIdioma()).toBe('pt')
  })

  it('elige español si es el idioma preferido', () => {
    stubNavegador({ languages: ['es-ES', 'en-US'] })
    expect(detectarIdioma()).toBe('es')
  })

  it('acepta la etiqueta sin región', () => {
    stubNavegador({ languages: ['pt'] })
    expect(detectarIdioma()).toBe('pt')
  })

  it('ignora las mayúsculas de la etiqueta', () => {
    stubNavegador({ languages: ['PT-BR'] })
    expect(detectarIdioma()).toBe('pt')
  })

  it('respeta el orden de preferencia del navegador', () => {
    stubNavegador({ languages: ['fr-FR', 'pt-PT', 'es-ES'] })
    expect(detectarIdioma()).toBe('pt')

    stubNavegador({ languages: ['fr-FR', 'es-419', 'pt-PT'] })
    expect(detectarIdioma()).toBe('es')
  })

  it('salta los idiomas que la aplicación no sirve', () => {
    stubNavegador({ languages: ['en-GB', 'de-DE', 'es-MX'] })
    expect(detectarIdioma()).toBe('es')
  })

  it('cae a español si ninguna preferencia está soportada', () => {
    stubNavegador({ languages: ['en-US', 'fr-FR'] })
    expect(detectarIdioma()).toBe('es')
  })

  it('cae a español si la lista de preferencias está vacía', () => {
    stubNavegador({ languages: [] })
    expect(detectarIdioma()).toBe('es')
  })

  it('usa navigator.language cuando el navegador no expone la lista', () => {
    stubNavegador({ language: 'pt-PT' })
    expect(detectarIdioma()).toBe('pt')
  })

  it('devuelve siempre un idioma que el router reconoce', () => {
    for (const preferencia of ['pt-BR', 'es-CL', 'ja-JP']) {
      stubNavegador({ languages: [preferencia] })
      expect(esIdioma(detectarIdioma())).toBe(true)
    }
  })
})

// --- Etiquetas de interfaz --------------------------------------------------

type Traducciones = Record<string, unknown>

/** Aplana el JSON de etiquetas a claves con puntos: `panel.columnas.estado`. */
function claves(objeto: Traducciones, prefijo = ''): string[] {
  return Object.entries(objeto).flatMap(([clave, valor]) =>
    typeof valor === 'object' && valor !== null
      ? claves(valor as Traducciones, `${prefijo}${clave}.`)
      : [`${prefijo}${clave}`],
  )
}

function textos(objeto: Traducciones, prefijo = ''): [string, string][] {
  return Object.entries(objeto).flatMap(([clave, valor]) =>
    typeof valor === 'object' && valor !== null
      ? textos(valor as Traducciones, `${prefijo}${clave}.`)
      : [[`${prefijo}${clave}`, String(valor)] as [string, string]],
  )
}

/** Marcadores de interpolación de i18next presentes en un texto. */
function marcadores(texto: string): string[] {
  return [...texto.matchAll(/\{\{(.*?)\}\}/g)].map(m => m[1].trim()).sort()
}

describe('recursos de i18next', () => {
  it('registra los dos idiomas de la aplicación en el espacio de nombres ui', () => {
    expect(Object.keys(recursos).sort()).toEqual([...IDIOMAS].sort())
    for (const idioma of IDIOMAS) {
      expect(recursos[idioma].ui).toBeTypeOf('object')
    }
  })

  it('traduce exactamente las mismas claves en español y portugués', () => {
    const enEs = claves(recursos.es.ui).sort()
    const enPt = claves(recursos.pt.ui).sort()

    // Se comparan en ambos sentidos para que el fallo diga qué idioma falta.
    expect(enPt.filter(c => !enEs.includes(c))).toEqual([])
    expect(enEs.filter(c => !enPt.includes(c))).toEqual([])
    expect(enPt).toEqual(enEs)
  })

  it('no deja ninguna etiqueta vacía en ningún idioma', () => {
    for (const idioma of IDIOMAS) {
      const vacias = textos(recursos[idioma].ui)
        .filter(([, valor]) => valor.trim() === '')
        .map(([clave]) => `${idioma}:${clave}`)
      expect(vacias).toEqual([])
    }
  })

  it('usa los mismos marcadores de interpolación en ambos idiomas', () => {
    const enPt = new Map(textos(recursos.pt.ui))
    const desajustes = textos(recursos.es.ui)
      .filter(([clave, valor]) => marcadores(valor).join() !== marcadores(enPt.get(clave) ?? '').join())
      .map(([clave]) => clave)
    // Un `{{count}}` perdido en la traducción imprime el marcador en pantalla.
    expect(desajustes).toEqual([])
  })

  it('declara las formas de plural que necesita i18next en los dos idiomas', () => {
    for (const idioma of IDIOMAS) {
      const declaradas = claves(recursos[idioma].ui)
      expect(declaradas).toContain('general.articulos_one')
      expect(declaradas).toContain('general.articulos_other')
      expect(declaradas).toContain('busqueda.resultados_one')
      expect(declaradas).toContain('busqueda.resultados_other')
    }
  })
})
