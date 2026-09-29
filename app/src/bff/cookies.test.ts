import { afterEach, describe, expect, it, vi } from 'vitest'
import { MAX_AGE_ACCESS, MAX_AGE_REFRESH, opcionesBorrado, opcionesCookie } from './cookies'

describe('opciones de cookie del BFF', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('la cookie es httpOnly, SameSite=Lax y con Path raíz', () => {
    const o = opcionesCookie(MAX_AGE_ACCESS)
    expect(o.httpOnly).toBe(true)
    expect(o.sameSite).toBe('lax')
    expect(o.path).toBe('/')
    expect(o.maxAge).toBe(MAX_AGE_ACCESS)
  })

  it('la cookie es host-only: no lleva Domain (aísla la sesión entre portales)', () => {
    // Sin `Domain`, la cookie queda atada al host exacto que la emitió, de modo que la
    // sesión de `cliente-a.tuapp.com` nunca se envía a `cliente-b.tuapp.com`. Un
    // `Domain=.tuapp.com` la filtraría entre subdominios: se comprueba que nunca aparece.
    expect(opcionesCookie(MAX_AGE_ACCESS)).not.toHaveProperty('domain')
    expect(opcionesBorrado()).not.toHaveProperty('domain')
  })

  it('Secure se activa solo en producción', () => {
    vi.stubEnv('NODE_ENV', 'production')
    expect(opcionesCookie(1).secure).toBe(true)
    vi.stubEnv('NODE_ENV', 'development')
    expect(opcionesCookie(1).secure).toBe(false)
  })

  it('el borrado expira la cookie de inmediato conservando httpOnly', () => {
    const o = opcionesBorrado()
    expect(o.maxAge).toBe(0)
    expect(o.httpOnly).toBe(true)
    expect(o.path).toBe('/')
  })

  it('el refresh vive más que el access', () => {
    expect(MAX_AGE_REFRESH).toBeGreaterThan(MAX_AGE_ACCESS)
  })
})
