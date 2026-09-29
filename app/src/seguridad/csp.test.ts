import { describe, expect, it } from 'vitest'
import { construirCSP } from './csp'

/** Extrae los valores de una directiva de la cadena CSP (`nombre v1 v2 …`). */
function directiva(csp: string, nombre: string): string[] {
  const parte = csp.split(';').map(p => p.trim()).find(p => p === nombre || p.startsWith(`${nombre} `))
  if (!parte) return []
  return parte.split(/\s+/).slice(1)
}

describe('construirCSP', () => {
  const csp = construirCSP('abc123')

  it('inserta el nonce recibido en script-src', () => {
    expect(directiva(csp, 'script-src')).toContain("'nonce-abc123'")
  })

  it('usa strict-dynamic para no depender de una lista blanca de dominios', () => {
    expect(directiva(csp, 'script-src')).toContain("'strict-dynamic'")
  })

  it('nunca permite scripts en línea (sin unsafe-inline en script-src)', () => {
    expect(directiva(csp, 'script-src')).not.toContain("'unsafe-inline'")
  })

  it('bloquea el embebido y los plugins', () => {
    expect(directiva(csp, 'frame-ancestors')).toEqual(["'none'"])
    expect(directiva(csp, 'object-src')).toEqual(["'none'"])
  })

  it('restringe el origen por defecto, la base de URLs y el envío de formularios', () => {
    expect(directiva(csp, 'default-src')).toEqual(["'self'"])
    expect(directiva(csp, 'base-uri')).toEqual(["'self'"])
    expect(directiva(csp, 'form-action')).toEqual(["'self'"])
  })

  it('cada nonce produce una directiva distinta', () => {
    expect(construirCSP('uno')).not.toEqual(construirCSP('dos'))
  })
})
