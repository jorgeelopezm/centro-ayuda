import { describe, expect, it } from 'vitest'
import { IDIOMAS, esIdioma } from '@/types'
import { rutas } from './rutas'

describe('rutas', () => {
  it('pone el idioma en el primer segmento', () => {
    expect(rutas.inicio('es')).toBe('/es')
    expect(rutas.inicio('pt')).toBe('/pt')
    expect(rutas.panel('es')).toBe('/es/panel')
    expect(rutas.panel('pt')).toBe('/pt/panel')
    expect(rutas.login('es')).toBe('/es/login')
    expect(rutas.login('pt')).toBe('/pt/login')
    expect(rutas.usuarios('es')).toBe('/es/panel/usuarios')
    expect(rutas.usuarios('pt')).toBe('/pt/panel/usuarios')
  })

  it('la gestión de usuarios cuelga del panel (ruta de Administrador anidada)', () => {
    // El router monta `panel/usuarios` bajo la guardia de Administrador; la dirección
    // construida tiene que coincidir con ese segmento.
    for (const idioma of IDIOMAS) {
      expect(rutas.usuarios(idioma)).toBe(`${rutas.panel(idioma)}/usuarios`)
    }
  })

  it('la entrada al panel interno lleva el segmento traducido y no cuelga de la guardia', () => {
    expect(rutas.panelInterno('es')).toBe('/es/panel-interno')
    expect(rutas.panelInterno('pt')).toBe('/pt/painel-interno')
    // No empieza por `/{idioma}/panel/`: la sirve una página que solo redirige al panel,
    // y es esa redirección la que pasa por la guardia del borde.
    for (const idioma of IDIOMAS) {
      expect(rutas.panelInterno(idioma).startsWith(`${rutas.panel(idioma)}/`)).toBe(false)
    }
  })

  it('construye la dirección de un artículo con su slug', () => {
    expect(rutas.articulo('es', 'plazos-de-devolucion')).toBe('/es/articulo/plazos-de-devolucion')
    expect(rutas.articulo('pt', 'prazos-de-devolucao')).toBe('/pt/articulo/prazos-de-devolucao')
  })

  it('genera direcciones absolutas para todos los idiomas', () => {
    for (const idioma of IDIOMAS) {
      expect(rutas.inicio(idioma).startsWith(`/${idioma}`)).toBe(true)
      expect(rutas.panel(idioma).startsWith(`/${idioma}`)).toBe(true)
      expect(rutas.login(idioma).startsWith(`/${idioma}`)).toBe(true)
      expect(rutas.articulo(idioma, 'x').startsWith(`/${idioma}`)).toBe(true)
    }
  })

  it('produce direcciones distintas por idioma para el mismo destino', () => {
    expect(rutas.panel('es')).not.toBe(rutas.panel('pt'))
  })

  it('escribe un primer segmento que el router reconoce como idioma', () => {
    // El guardia del panel valida `params.idioma` con `esIdioma`: lo que
    // construyen estas funciones tiene que pasar por ahí.
    for (const idioma of IDIOMAS) {
      const direcciones = [
        rutas.inicio(idioma),
        rutas.panel(idioma),
        rutas.login(idioma),
        rutas.articulo(idioma, 'plazos-de-devolucion'),
      ]
      for (const direccion of direcciones) {
        expect(esIdioma(direccion.split('/')[1])).toBe(true)
      }
    }
  })

  it('cuelga el artículo del idioma y del segmento articulo', () => {
    // La forma de la dirección la comparten las citas del asistente y el
    // enrutado (`/:idioma/articulo/:slug`): cambiarla rompe los enlaces citados.
    expect(rutas.articulo('pt', 'prazos-de-devolucao').split('/')).toEqual([
      '',
      'pt',
      'articulo',
      'prazos-de-devolucao',
    ])
  })

  it('conserva el slug tal cual, sin añadir barra final', () => {
    expect(rutas.articulo('es', 'plazos-de-devolucion').endsWith('/')).toBe(false)
    expect(rutas.inicio('es').endsWith('/')).toBe(false)
  })
})
