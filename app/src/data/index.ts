import type { Articulo, ContenidoIdioma, IdCategoria, Idioma } from '@/types'

/**
 * Punto único de acceso al contenido. Antes servía módulos estáticos; ahora
 * consulta la API (`GET /api/{idioma}/contenido`). La forma del `ContenidoIdioma`
 * no cambia, así que las funciones derivadas y los componentes siguen igual.
 */
export async function cargarContenido(idioma: Idioma): Promise<ContenidoIdioma> {
  const resp = await fetch(`/api/${idioma}/contenido`)
  if (!resp.ok) {
    throw new Response(`No se pudo cargar el contenido (${resp.status})`, { status: resp.status })
  }
  return (await resp.json()) as ContenidoIdioma
}

export type ContenidoPorIdioma = Record<Idioma, ContenidoIdioma>

/**
 * Loader de ruta: carga ambos idiomas antes de renderizar. Se cargan los dos
 * porque el selector de idioma necesita el contenido del idioma destino para
 * construir la dirección equivalente de un artículo.
 */
export async function cargarContenidoLoader(): Promise<ContenidoPorIdioma> {
  const [es, pt] = await Promise.all([cargarContenido('es'), cargarContenido('pt')])
  return { es, pt }
}

/**
 * Conteo de artículos por categoría derivado de los datos. Evita que las
 * tarjetas muestren un número que contradiga al buscador.
 */
export function contarPorCategoria(articulos: Articulo[]): Record<IdCategoria, number> {
  return articulos.reduce(
    (acc, articulo) => {
      acc[articulo.categoria] = (acc[articulo.categoria] ?? 0) + 1
      return acc
    },
    {} as Record<IdCategoria, number>,
  )
}

export function articuloPorSlug(contenido: ContenidoIdioma, slug: string): Articulo | undefined {
  return contenido.articulos.find(a => a.slug === slug)
}

export function articuloPorId(contenido: ContenidoIdioma, id: string): Articulo | undefined {
  return contenido.articulos.find(a => a.id === id)
}

export function articulosDestacados(contenido: ContenidoIdioma): Articulo[] {
  return contenido.articulos.filter(a => a.destacado)
}

function normalizar(texto: string): string {
  return texto
    .toLocaleLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

/**
 * Búsqueda en cliente por título y nombre de categoría, insensible a
 * mayúsculas y acentos. Con este volumen de artículos no hace falta más.
 */
export function buscarArticulos(contenido: ContenidoIdioma, termino: string): Articulo[] {
  const consulta = normalizar(termino.trim())
  if (consulta === '') return []

  const nombreCategoria = new Map(contenido.categorias.map(c => [c.id, normalizar(c.nombre)]))

  return contenido.articulos.filter(articulo => {
    const titulo = normalizar(articulo.titulo)
    const categoria = nombreCategoria.get(articulo.categoria) ?? ''
    return titulo.includes(consulta) || categoria.includes(consulta)
  })
}
