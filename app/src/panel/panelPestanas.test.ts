import { describe, expect, it } from 'vitest'
import { PESTANAS, resolverPestana } from './panelPestanas'

describe('PESTANAS', () => {
  it('orden final incluye chats y sugerencias entre gestion y categorias', () => {
    expect(PESTANAS).toEqual(['sinResolver', 'gestion', 'chats', 'sugerencias', 'categorias', 'admin'])
  })
})

describe('resolverPestana', () => {
  it('sin parámetro cae a la pestaña por defecto', () => {
    expect(resolverPestana(null, false)).toBe('sinResolver')
    expect(resolverPestana(null, true)).toBe('sinResolver')
  })

  it('un valor desconocido cae a la pestaña por defecto', () => {
    expect(resolverPestana('otra', true)).toBe('sinResolver')
    expect(resolverPestana('', true)).toBe('sinResolver')
  })

  it('devuelve una pestaña válida no restringida tal cual', () => {
    expect(resolverPestana('sinResolver', false)).toBe('sinResolver')
    expect(resolverPestana('gestion', false)).toBe('gestion')
  })

  it('categorias está disponible para Editor (sin Administrador)', () => {
    expect(resolverPestana('categorias', false)).toBe('categorias')
    expect(resolverPestana('categorias', true)).toBe('categorias')
  })

  it('chats está disponible para Editor y para Administrador', () => {
    expect(resolverPestana('chats', false)).toBe('chats')
    expect(resolverPestana('chats', true)).toBe('chats')
  })

  it('sugerencias está disponible para Editor y para Administrador', () => {
    expect(resolverPestana('sugerencias', false)).toBe('sugerencias')
    expect(resolverPestana('sugerencias', true)).toBe('sugerencias')
  })

  it('admin solo se resuelve cuando la sesión es Administrador', () => {
    expect(resolverPestana('admin', true)).toBe('admin')
  })

  it('admin sin Administrador cae a la pestaña por defecto (no se expone por URL)', () => {
    expect(resolverPestana('admin', false)).toBe('sinResolver')
  })
})
