import { describe, expect, it } from 'vitest'
import {
  AA_NORMAL,
  BLANCO,
  derivarDegradadoBanner,
  derivarTokensAcento,
  derivarTokensAcentoNoche,
  FONDO_NOCHE,
  HOVER_NOCHE,
  hexARgb,
  luminanciaRelativa,
  ratioContraste,
  validarPaleta,
} from './contraste'

const ACENTO_DEFECTO = '#4338ca'
const BANNER_DEFECTO: [string, string, string] = ['#3730a3', '#4338ca', '#4f46e5']
// Acentos que superan la validación COMPLETA de paleta (botón, tinte, foco). Un gris muy
// desaturado como #767676 cumple 4.5:1 con blanco pero falla el par acento/tinte, así que
// no es un acento de marca válido; su caso límite se prueba aparte solo contra el blanco.
const ACENTOS_VALIDOS = ['#4338ca', '#0f766e', '#b91c1c', '#7c3aed', '#1d4ed8']

describe('fórmulas de contraste', () => {
  it('expande el hex de tres dígitos', () => {
    expect(hexARgb('#fff')).toEqual([255, 255, 255])
    expect(hexARgb('#000')).toEqual([0, 0, 0])
  })

  it('rechaza hex inválidos', () => {
    for (const malo of ['blanco', '#12', '#1234', 'rgb(0,0,0)', '#ggghhh']) {
      expect(() => hexARgb(malo)).toThrow()
    }
  })

  it('luminancia en los extremos', () => {
    expect(luminanciaRelativa('#000000')).toBeCloseTo(0, 6)
    expect(luminanciaRelativa('#ffffff')).toBeCloseTo(1, 6)
  })

  it('blanco vs negro da 21:1', () => {
    expect(ratioContraste('#000000', '#ffffff')).toBeCloseTo(21, 1)
  })

  it('el ratio es simétrico', () => {
    expect(ratioContraste('#4338ca', '#ffffff')).toBeCloseTo(ratioContraste('#ffffff', '#4338ca'), 6)
  })

  it('gris límite AA', () => {
    expect(ratioContraste('#767676', '#ffffff')).toBeGreaterThanOrEqual(AA_NORMAL)
    expect(ratioContraste('#787878', '#ffffff')).toBeLessThan(AA_NORMAL)
  })
})

describe('derivación de tokens', () => {
  it('devuelve hex válidos y hover más oscuro / claro más luminoso', () => {
    const tokens = derivarTokensAcento(ACENTO_DEFECTO)
    expect(() => hexARgb(tokens.hover)).not.toThrow()
    expect(() => hexARgb(tokens.claro)).not.toThrow()
    expect(() => hexARgb(tokens.foco)).not.toThrow()
    const base = luminanciaRelativa(ACENTO_DEFECTO)
    expect(luminanciaRelativa(tokens.hover)).toBeLessThan(base)
    expect(luminanciaRelativa(tokens.claro)).toBeGreaterThan(base)
  })
})

describe('derivación del degradado del banner', () => {
  // Referencia compartida con Python (test_contraste.py): misma fórmula ⇒ mismo hex.
  const BANNER_DERIVADO_DEFECTO = { desde: '#4338ca', medio: '#372eac', hasta: '#2d258b' }

  it('la parada inicial es el propio acento', () => {
    expect(derivarDegradadoBanner(ACENTO_DEFECTO).desde).toBe(ACENTO_DEFECTO)
  })

  it('reproduce la referencia compartida con el servidor (paridad)', () => {
    expect(derivarDegradadoBanner(ACENTO_DEFECTO)).toEqual(BANNER_DERIVADO_DEFECTO)
  })

  it.each(ACENTOS_VALIDOS)('cada parada derivada de %s contrasta con blanco', acento => {
    expect(ratioContraste(BLANCO, acento)).toBeGreaterThanOrEqual(AA_NORMAL) // precondición
    const banner = derivarDegradadoBanner(acento)
    for (const parada of Object.values(banner)) {
      expect(ratioContraste(BLANCO, parada)).toBeGreaterThanOrEqual(AA_NORMAL)
    }
  })

  it.each(ACENTOS_VALIDOS)('la luminosidad decrece hacia el final (%s)', acento => {
    const { desde, medio, hasta } = derivarDegradadoBanner(acento)
    expect(luminanciaRelativa(desde)).toBeGreaterThanOrEqual(luminanciaRelativa(medio))
    expect(luminanciaRelativa(medio)).toBeGreaterThanOrEqual(luminanciaRelativa(hasta))
  })

  it.each(ACENTOS_VALIDOS)('el degradado derivado de %s valida la paleta', acento => {
    const { desde, medio, hasta } = derivarDegradadoBanner(acento)
    expect(validarPaleta(acento, desde, medio, hasta)).toBeNull()
  })

  it('un acento gris al borde de 4.5:1 mantiene el banner accesible con blanco', () => {
    // #767676 roza el mínimo con blanco; las paradas (más oscuras) lo mantienen, aunque
    // el gris no sea un acento de marca válido por otras razones (par acento/tinte).
    expect(ratioContraste(BLANCO, '#767676')).toBeGreaterThanOrEqual(AA_NORMAL)
    for (const parada of Object.values(derivarDegradadoBanner('#767676'))) {
      expect(ratioContraste(BLANCO, parada)).toBeGreaterThanOrEqual(AA_NORMAL)
    }
  })
})

describe('validación de paleta', () => {
  it('la paleta por defecto cumple', () => {
    expect(validarPaleta(ACENTO_DEFECTO, ...BANNER_DEFECTO)).toBeNull()
  })

  it('un acento demasiado claro falla el botón', () => {
    const fallo = validarPaleta('#cccccc', ...BANNER_DEFECTO)
    expect(fallo).not.toBeNull()
    expect(fallo!.par.toLowerCase()).toContain('botón')
    expect(fallo!.ratio).toBeLessThan(fallo!.minimo)
  })

  it('un banner demasiado claro falla', () => {
    const fallo = validarPaleta(ACENTO_DEFECTO, '#3730a3', '#4338ca', '#fffbe6')
    expect(fallo).not.toBeNull()
    expect(fallo!.par.toLowerCase()).toContain('banner')
  })

  it('un color inválido lanza', () => {
    expect(() => validarPaleta('no-es-hex', ...BANNER_DEFECTO)).toThrow()
  })
})

describe('escala de acento del modo noche', () => {
  // Incluye el verde del portal de ejemplo y un acento casi negro (peor caso).
  const ACENTOS = [...ACENTOS_VALIDOS, '#2e7d32', '#111111']

  it.each(ACENTOS)('el texto de acento cumple AA sobre toda superficie oscura (%s)', acento => {
    const noche = derivarTokensAcentoNoche(acento)
    for (const fondo of [FONDO_NOCHE, HOVER_NOCHE, noche.claro]) {
      expect(ratioContraste(noche.acento, fondo)).toBeGreaterThanOrEqual(AA_NORMAL)
    }
  })

  it.each(ACENTOS)('el texto oscuro sobre el botón de acento y su hover cumple AA (%s)', acento => {
    // En modo noche el «blanco» de los botones es la superficie oscura.
    const noche = derivarTokensAcentoNoche(acento)
    expect(ratioContraste(FONDO_NOCHE, noche.acento)).toBeGreaterThanOrEqual(AA_NORMAL)
    expect(ratioContraste(FONDO_NOCHE, noche.hover)).toBeGreaterThanOrEqual(AA_NORMAL)
  })

  it.each(ACENTOS)('el anillo de foco supera 3:1 sobre el fondo oscuro (%s)', acento => {
    expect(ratioContraste(derivarTokensAcentoNoche(acento).foco, FONDO_NOCHE)).toBeGreaterThanOrEqual(3)
  })

  it('el fondo tenue conserva el tono del acento y sigue siendo oscuro', () => {
    const { claro } = derivarTokensAcentoNoche(ACENTO_DEFECTO)
    expect(luminanciaRelativa(claro)).toBeLessThan(luminanciaRelativa(HOVER_NOCHE) * 2)
    expect(claro).not.toBe(FONDO_NOCHE)
  })

  it('no toca un acento que ya cumple sobre fondo oscuro', () => {
    expect(derivarTokensAcentoNoche('#fbbf24').acento).toBe('#fbbf24')
    expect(BLANCO).toBe('#ffffff')
  })
})
