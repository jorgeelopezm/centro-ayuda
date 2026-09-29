import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Articulo, Categoria, ContenidoIdioma, IdCategoria } from '@/types'
import {
  articuloPorId,
  articuloPorSlug,
  articulosDestacados,
  buscarArticulos,
  cargarContenido,
  cargarContenidoLoader,
  contarPorCategoria,
} from './index'

// --- Fixtures ---------------------------------------------------------------

const categorias: Categoria[] = [
  { id: 'cuenta', slug: 'cuenta', nombre: 'Cuenta', icono: 'usuario' },
  { id: 'envios', slug: 'envios', nombre: 'Envíos', icono: 'paquete' },
  { id: 'pagos', slug: 'pagos', nombre: 'Pagos', icono: 'tarjeta' },
]

function articulo(
  id: string,
  slug: string,
  titulo: string,
  categoria: IdCategoria,
  destacado = false,
): Articulo {
  return {
    id,
    slug,
    titulo,
    categoria,
    actualizado: '2026-07-20',
    minutosLectura: 2,
    destacado,
    parrafos: ['Un párrafo.'],
    howTo: { titulo: 'Pasos', pasos: [{ titulo: 'Paso 1', descripcion: 'Hazlo.' }] },
    faq: [{ pregunta: '¿Y?', respuesta: 'Pues eso.' }],
    relacionados: [],
  }
}

const articulos: Articulo[] = [
  articulo('restablecer-contrasena', 'restablecer-mi-contrasena', 'Cómo restablecer mi contraseña', 'cuenta', true),
  articulo('cerrar-cuenta', 'cerrar-mi-cuenta', 'Cómo cerrar tu cuenta', 'cuenta'),
  articulo('seguimiento-pedido', 'seguimiento-de-pedido', 'Seguimiento de pedido en tiempo real', 'envios', true),
]

const contenido: ContenidoIdioma = {
  empresa: '[Empresa]',
  acento: '#4338ca',
  bannerDesde: '#3730a3',
  bannerMedio: '#4338ca',
  bannerHasta: '#4f46e5',
  plantilla: 'default',
  logo: false,
  logoVersion: null,
  categorias,
  articulos,
  conversacion: [],
  metricas: [],
}

// --- Funciones derivadas ----------------------------------------------------

describe('contarPorCategoria', () => {
  it('cuenta los artículos de cada categoría presente', () => {
    expect(contarPorCategoria(articulos)).toEqual({ cuenta: 2, envios: 1 })
  })

  it('omite las categorías sin artículos en vez de ponerlas a cero', () => {
    // El componente resuelve el hueco con `?? 0`; el conteo no lo inventa.
    expect(contarPorCategoria(articulos)).not.toHaveProperty('pagos')
  })

  it('devuelve un objeto vacío sin artículos', () => {
    expect(contarPorCategoria([])).toEqual({})
  })
})

describe('articuloPorSlug', () => {
  it('encuentra el artículo por su segmento de dirección', () => {
    expect(articuloPorSlug(contenido, 'cerrar-mi-cuenta')?.id).toBe('cerrar-cuenta')
  })

  it('devuelve undefined si el slug no existe', () => {
    expect(articuloPorSlug(contenido, 'no-existe')).toBeUndefined()
  })

  it('no confunde el slug con el identificador', () => {
    // 'cerrar-cuenta' es el id, no el slug: buscar por slug no debe encontrarlo.
    expect(articuloPorSlug(contenido, 'cerrar-cuenta')).toBeUndefined()
  })
})

describe('articuloPorId', () => {
  it('encuentra el artículo por su identificador estable', () => {
    expect(articuloPorId(contenido, 'seguimiento-pedido')?.slug).toBe('seguimiento-de-pedido')
  })

  it('devuelve undefined si el identificador no existe', () => {
    expect(articuloPorId(contenido, 'inventado')).toBeUndefined()
  })
})

describe('articulosDestacados', () => {
  it('devuelve solo los marcados como destacados', () => {
    expect(articulosDestacados(contenido).map(a => a.id)).toEqual([
      'restablecer-contrasena',
      'seguimiento-pedido',
    ])
  })

  it('devuelve una lista vacía si ninguno está destacado', () => {
    const sinDestacados = { ...contenido, articulos: articulos.map(a => ({ ...a, destacado: false })) }
    expect(articulosDestacados(sinDestacados)).toEqual([])
  })
})

describe('buscarArticulos', () => {
  it('encuentra por título', () => {
    expect(buscarArticulos(contenido, 'contraseña').map(a => a.id)).toEqual(['restablecer-contrasena'])
  })

  it('ignora mayúsculas', () => {
    expect(buscarArticulos(contenido, 'CONTRASEÑA').map(a => a.id)).toEqual(['restablecer-contrasena'])
  })

  it('ignora los acentos en ambos sentidos', () => {
    // Sin tilde en la consulta, con tilde en el título.
    expect(buscarArticulos(contenido, 'contrasena').map(a => a.id)).toEqual(['restablecer-contrasena'])
    // Con tilde en la consulta, sin tilde en el nombre de categoría normalizado.
    expect(buscarArticulos(contenido, 'envíos').map(a => a.id)).toEqual(['seguimiento-pedido'])
  })

  it('encuentra por nombre de categoría', () => {
    expect(buscarArticulos(contenido, 'cuenta').map(a => a.id)).toEqual([
      'restablecer-contrasena',
      'cerrar-cuenta',
    ])
  })

  it('devuelve lista vacía con término vacío o solo espacios', () => {
    expect(buscarArticulos(contenido, '')).toEqual([])
    expect(buscarArticulos(contenido, '   ')).toEqual([])
  })

  it('recorta los espacios alrededor del término', () => {
    expect(buscarArticulos(contenido, '  pedido  ').map(a => a.id)).toEqual(['seguimiento-pedido'])
  })

  it('devuelve lista vacía si nada coincide', () => {
    expect(buscarArticulos(contenido, 'criptomonedas')).toEqual([])
  })

  it('busca por subcadena, no solo por palabra completa', () => {
    expect(buscarArticulos(contenido, 'segui').map(a => a.id)).toEqual(['seguimiento-pedido'])
  })

  it('no repite un artículo que coincide a la vez por título y por categoría', () => {
    // 'cerrar-cuenta' coincide por su título y por el nombre de su categoría.
    const ids = buscarArticulos(contenido, 'cuenta').map(a => a.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('sigue buscando por título si la categoría del artículo no está declarada', () => {
    const huerfano = articulo('factura-mensual', 'descargar-factura', 'Cómo descargar tu factura', 'facturacion')
    const conHuerfano = { ...contenido, articulos: [...articulos, huerfano] }

    expect(buscarArticulos(conHuerfano, 'factura').map(a => a.id)).toEqual(['factura-mensual'])
    // Sin categoría declarada no hay nombre que emparejar: no revienta, no coincide.
    expect(buscarArticulos(conHuerfano, 'facturacion')).toEqual([])
  })

  it('no altera el contenido recibido', () => {
    const antes = contenido.articulos.map(a => a.id)

    const resultado = buscarArticulos(contenido, 'cuenta')

    expect(resultado).not.toBe(contenido.articulos)
    expect(contenido.articulos.map(a => a.id)).toEqual(antes)
  })
})

// --- Acceso a la API --------------------------------------------------------

describe('cargarContenido', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('pide el contenido del idioma y devuelve el cuerpo', async () => {
    const fetchDoble = vi.fn(async (_url: string) => new Response(JSON.stringify(contenido), { status: 200 }))
    vi.stubGlobal('fetch', fetchDoble)

    const recibido = await cargarContenido('pt')

    expect(fetchDoble).toHaveBeenCalledWith('/api/pt/contenido')
    expect(recibido.articulos).toHaveLength(3)
  })

  it('lanza una Response con el estado del error si la petición falla', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: string) => new Response(null, { status: 503 })))

    await expect(cargarContenido('es')).rejects.toBeInstanceOf(Response)
    await expect(cargarContenido('es')).rejects.toMatchObject({ status: 503 })
  })
})

describe('cargarContenidoLoader', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('carga los dos idiomas y los devuelve indexados', async () => {
    const fetchDoble = vi.fn(async (_url: string) => new Response(JSON.stringify(contenido), { status: 200 }))
    vi.stubGlobal('fetch', fetchDoble)

    const ambos = await cargarContenidoLoader()

    // El selector de idioma necesita el contenido del idioma destino.
    expect(Object.keys(ambos).sort()).toEqual(['es', 'pt'])
    expect(fetchDoble).toHaveBeenCalledWith('/api/es/contenido')
    expect(fetchDoble).toHaveBeenCalledWith('/api/pt/contenido')
  })

  it('propaga el fallo si alguno de los dos idiomas falla', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url.includes('/pt/')
          ? new Response(null, { status: 500 })
          : new Response(JSON.stringify(contenido), { status: 200 }),
      ),
    )

    await expect(cargarContenidoLoader()).rejects.toBeInstanceOf(Response)
  })
})
