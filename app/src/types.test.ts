import { describe, expect, it } from 'vitest'
import { IDIOMAS, esIdioma } from './types'

describe('IDIOMAS', () => {
  it('declara español y portugués, en ese orden', () => {
    expect(IDIOMAS).toEqual(['es', 'pt'])
  })
})

describe('esIdioma', () => {
  it('acepta los idiomas de la aplicación', () => {
    expect(esIdioma('es')).toBe(true)
    expect(esIdioma('pt')).toBe(true)
  })

  it('rechaza cualquier otro valor', () => {
    expect(esIdioma('fr')).toBe(false)
    expect(esIdioma('en')).toBe(false)
    expect(esIdioma('')).toBe(false)
    expect(esIdioma('ES')).toBe(false) // distingue mayúsculas: la dirección va en minúscula
    expect(esIdioma('panel')).toBe(false)
  })

  it('rechaza undefined (parámetro de ruta ausente)', () => {
    expect(esIdioma(undefined)).toBe(false)
  })

  it('acepta todos los idiomas declarados en IDIOMAS', () => {
    for (const idioma of IDIOMAS) {
      expect(esIdioma(idioma)).toBe(true)
    }
  })
})
