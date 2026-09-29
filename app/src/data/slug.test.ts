import { describe, expect, it } from 'vitest'
import { derivarId, derivarSlug, normalizarSlug } from './slug'

describe('normalizarSlug', () => {
  it('pasa a minúsculas y une con guiones', () => {
    expect(normalizarSlug('Plazos De Devolucion')).toBe('plazos-de-devolucion')
  })

  it('quita los acentos', () => {
    expect(normalizarSlug('Cómo cambiar tu contraseña')).toBe('como-cambiar-tu-contrasena')
  })

  it('convierte la ñ en n', () => {
    expect(normalizarSlug('Año español')).toBe('ano-espanol')
  })

  it('colapsa signos y espacios repetidos en un solo guion', () => {
    expect(normalizarSlug('Hola,  mundo!! ¿qué tal?')).toBe('hola-mundo-que-tal')
  })

  it('recorta los guiones de los extremos', () => {
    expect(normalizarSlug('  ¡Hola!  ')).toBe('hola')
  })

  it('conserva los dígitos', () => {
    expect(normalizarSlug('Envío en 24 horas')).toBe('envio-en-24-horas')
  })

  it('un texto sin caracteres válidos queda vacío', () => {
    expect(normalizarSlug('¿!  ¡?')).toBe('')
  })

  it('es idempotente sobre un slug ya normalizado', () => {
    expect(normalizarSlug('plazos-de-devolucion')).toBe('plazos-de-devolucion')
  })
})

describe('derivarId y derivarSlug', () => {
  it('derivan el mismo valor que normalizarSlug', () => {
    expect(derivarId('Cómo cambiar la contraseña')).toBe('como-cambiar-la-contrasena')
    expect(derivarSlug('Alterar a senha')).toBe('alterar-a-senha')
  })
})
