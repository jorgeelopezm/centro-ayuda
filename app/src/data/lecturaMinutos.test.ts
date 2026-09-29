import { describe, expect, it } from 'vitest'
import {
  contarPalabras,
  minutosDeArticulo,
  minutosDePalabras,
  minutosDeTraduccion,
} from './lecturaMinutos'
import type { TradDraft } from './articuloBorrador'

function trad(parrafos: string): TradDraft {
  return { slug: '', titulo: '', parrafos, nota: '', howToTitulo: '', pasos: [], faq: [] }
}

/** Genera un texto con exactamente `n` palabras. */
function palabras(n: number): string {
  return Array.from({ length: n }, (_, i) => `p${i}`).join(' ')
}

describe('contarPalabras', () => {
  it('cuenta separando por espacios', () => {
    expect(contarPalabras('uno dos tres')).toBe(3)
  })

  it('ignora espacios de más y los extremos', () => {
    expect(contarPalabras('  uno   dos  ')).toBe(2)
  })

  it('el texto vacío cuenta cero', () => {
    expect(contarPalabras('   ')).toBe(0)
  })
})

describe('minutosDePalabras', () => {
  it('unas 400 palabras dan 2 minutos', () => {
    expect(minutosDePalabras(400)).toBe(2)
  })

  it('menos de 200 palabras dan al menos 1 minuto', () => {
    expect(minutosDePalabras(150)).toBe(1)
    expect(minutosDePalabras(10)).toBe(1)
  })

  it('cero palabras siguen siendo 1 minuto (mínimo)', () => {
    expect(minutosDePalabras(0)).toBe(1)
  })
})

describe('minutosDeTraduccion', () => {
  it('suma todo el contenido legible de la traducción', () => {
    const t: TradDraft = {
      slug: 'x',
      titulo: 'Un título corto',
      parrafos: palabras(300),
      nota: '',
      howToTitulo: 'Pasos',
      pasos: [{ titulo: 'Paso', descripcion: palabras(100) }],
      faq: [],
    }
    // 300 + 100 + títulos ~ >400 palabras -> 2 minutos.
    expect(minutosDeTraduccion(t)).toBe(2)
  })
})

describe('minutosDeArticulo', () => {
  it('toma el idioma con más contenido', () => {
    const es = trad(palabras(600)) // ~3 min
    const pt = trad(palabras(100)) // 1 min
    expect(minutosDeArticulo(es, pt)).toBe(3)
  })
})
