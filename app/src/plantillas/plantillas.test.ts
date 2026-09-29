import { describe, expect, it } from 'vitest'
import { PLANTILLAS, PLANTILLA_POR_DEFECTO, esRutaAdministracion, resolverPlantilla } from './plantillas'

describe('PLANTILLAS', () => {
  it('declara las dos plantillas admitidas, con la predeterminada en la lista', () => {
    expect(PLANTILLAS).toEqual(['default', 'documentacion'])
    expect(PLANTILLAS).toContain(PLANTILLA_POR_DEFECTO)
  })
})

describe('resolverPlantilla', () => {
  it('devuelve la plantilla admitida tal cual', () => {
    expect(resolverPlantilla('default')).toBe('default')
    expect(resolverPlantilla('documentacion')).toBe('documentacion')
  })

  it('un valor desconocido cae a la plantilla predeterminada', () => {
    expect(resolverPlantilla('compacta')).toBe('default')
    expect(resolverPlantilla('')).toBe('default')
    expect(resolverPlantilla('DOCUMENTACION')).toBe('default') // distingue mayúsculas
  })

  it('un valor ausente cae a la plantilla predeterminada', () => {
    expect(resolverPlantilla(null)).toBe('default')
    expect(resolverPlantilla(undefined)).toBe('default')
  })

  it('la plantilla predeterminada se resuelve igual si la API la publica expresa', () => {
    // El respaldo no depende de que el campo falte: con el valor explícito, el resultado
    // es el mismo, así que el portal sin elección no cambia de aspecto.
    expect(resolverPlantilla('default')).toBe(PLANTILLA_POR_DEFECTO)
  })
})

describe('esRutaAdministracion', () => {
  it('reconoce el panel interno y sus subpantallas', () => {
    expect(esRutaAdministracion('/es/panel', 'es')).toBe(true)
    expect(esRutaAdministracion('/es/panel/usuarios', 'es')).toBe(true)
    expect(esRutaAdministracion('/es/panel/portales', 'es')).toBe(true)
  })

  it('reconoce el login, que es la puerta del panel', () => {
    expect(esRutaAdministracion('/es/login', 'es')).toBe(true)
    expect(esRutaAdministracion('/pt/login', 'pt')).toBe(true)
  })

  it('el idioma importa: la misma ruta en otro idioma no es la administración del activo', () => {
    expect(esRutaAdministracion('/pt/panel', 'es')).toBe(false)
    expect(esRutaAdministracion('/es/panel', 'pt')).toBe(false)
  })

  it('no confunde el sitio público con la administración', () => {
    expect(esRutaAdministracion('/es', 'es')).toBe(false)
    expect(esRutaAdministracion('/es/articulo/restablecer-mi-contrasena', 'es')).toBe(false)
    // Borde: una ruta que solo empieza por el prefijo no es el panel.
    expect(esRutaAdministracion('/es/panelx', 'es')).toBe(false)
    expect(esRutaAdministracion('/es/loginx', 'es')).toBe(false)
  })
})
