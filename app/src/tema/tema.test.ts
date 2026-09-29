import { describe, expect, it } from 'vitest'
import { alternarTema, cookieTema, esOscuro, resolverTema } from './tema'

describe('tema (modo noche)', () => {
  it('resuelve los valores admitidos y cae a `sistema` en cualquier otro', () => {
    expect(resolverTema('claro')).toBe('claro')
    expect(resolverTema('oscuro')).toBe('oscuro')
    for (const valor of [undefined, null, '', 'dark', 'OSCURO', '<script>']) {
      expect(resolverTema(valor)).toBe('sistema')
    }
  })

  it('`sistema` sigue la preferencia del sistema; los fijos la ignoran', () => {
    expect(esOscuro('sistema', true)).toBe(true)
    expect(esOscuro('sistema', false)).toBe(false)
    expect(esOscuro('oscuro', false)).toBe(true)
    expect(esOscuro('claro', true)).toBe(false)
  })

  it('el botón fija el contrario de lo que se ve', () => {
    expect(alternarTema(true)).toBe('claro')
    expect(alternarTema(false)).toBe('oscuro')
  })

  it('la cookie vale para todo el host y solo se marca Secure bajo https', () => {
    expect(cookieTema('oscuro', false)).toBe('tema=oscuro; Path=/; Max-Age=31536000; SameSite=Lax')
    expect(cookieTema('claro', true)).toMatch(/; Secure$/)
  })
})
