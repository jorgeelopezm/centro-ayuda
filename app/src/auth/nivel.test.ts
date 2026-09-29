import { describe, expect, it } from 'vitest'
import { NivelAcceso, esAdministrador, esSuperAdmin, tieneNivel } from './nivel'

describe('NivelAcceso (valores y orden)', () => {
  it('fija los cuatro valores enteros del enum', () => {
    // El valor entero es contrato con el backend (`NivelAcceso` en models.py) y ordena
    // la herencia. Un cambio silencioso aquí rompería la autorización: se fija en el test.
    expect(NivelAcceso.ANONIMO).toBe(1)
    expect(NivelAcceso.EDITOR).toBe(2)
    expect(NivelAcceso.ADMINISTRADOR).toBe(3)
    expect(NivelAcceso.SUPERADMIN).toBe(4)
  })

  it('los niveles crecen estrictamente Anónimo < Editor < Administrador < SuperAdmin', () => {
    expect(NivelAcceso.ANONIMO).toBeLessThan(NivelAcceso.EDITOR)
    expect(NivelAcceso.EDITOR).toBeLessThan(NivelAcceso.ADMINISTRADOR)
    expect(NivelAcceso.ADMINISTRADOR).toBeLessThan(NivelAcceso.SUPERADMIN)
  })
})

describe('tieneNivel', () => {
  it('sin sesión (null/undefined) no alcanza ningún recurso de administración', () => {
    expect(tieneNivel(null, NivelAcceso.EDITOR)).toBe(false)
    expect(tieneNivel(undefined, NivelAcceso.EDITOR)).toBe(false)
    expect(tieneNivel(null, NivelAcceso.ADMINISTRADOR)).toBe(false)
  })

  it('el nivel exacto alcanza su propio requisito', () => {
    expect(tieneNivel(NivelAcceso.EDITOR, NivelAcceso.EDITOR)).toBe(true)
    expect(tieneNivel(NivelAcceso.ADMINISTRADOR, NivelAcceso.ADMINISTRADOR)).toBe(true)
  })

  it('la jerarquía es estricta: Administrador hereda lo de Editor, no al revés', () => {
    // Administrador (3) satisface un requisito de Editor (2).
    expect(tieneNivel(NivelAcceso.ADMINISTRADOR, NivelAcceso.EDITOR)).toBe(true)
    // Editor (2) no llega a un recurso de Administrador (3).
    expect(tieneNivel(NivelAcceso.EDITOR, NivelAcceso.ADMINISTRADOR)).toBe(false)
  })

  it('SuperAdmin (4) hereda todo lo inferior; nadie inferior alcanza a SuperAdmin', () => {
    expect(tieneNivel(NivelAcceso.SUPERADMIN, NivelAcceso.ADMINISTRADOR)).toBe(true)
    expect(tieneNivel(NivelAcceso.SUPERADMIN, NivelAcceso.EDITOR)).toBe(true)
    expect(tieneNivel(NivelAcceso.SUPERADMIN, NivelAcceso.SUPERADMIN)).toBe(true)
    expect(tieneNivel(NivelAcceso.ADMINISTRADOR, NivelAcceso.SUPERADMIN)).toBe(false)
  })
})

describe('esAdministrador', () => {
  it('es verdadero para Administrador y para SuperAdmin (que lo hereda)', () => {
    expect(esAdministrador(NivelAcceso.ADMINISTRADOR)).toBe(true)
    expect(esAdministrador(NivelAcceso.SUPERADMIN)).toBe(true)
    expect(esAdministrador(NivelAcceso.EDITOR)).toBe(false)
    expect(esAdministrador(null)).toBe(false)
  })
})

describe('esSuperAdmin', () => {
  it('solo es verdadero para el nivel SuperAdmin', () => {
    expect(esSuperAdmin(NivelAcceso.SUPERADMIN)).toBe(true)
    expect(esSuperAdmin(NivelAcceso.ADMINISTRADOR)).toBe(false)
    expect(esSuperAdmin(NivelAcceso.EDITOR)).toBe(false)
    expect(esSuperAdmin(null)).toBe(false)
    expect(esSuperAdmin(undefined)).toBe(false)
  })
})
