/**
 * Contrato de datos del centro de ayuda.
 *
 * Hoy lo satisfacen los módulos de `src/data/<idioma>/`. Cuando exista la API,
 * estos mismos tipos describen sus respuestas y los componentes no cambian.
 */

export const IDIOMAS = ['es', 'pt'] as const
export type Idioma = (typeof IDIOMAS)[number]

export function esIdioma(valor: string | undefined): valor is Idioma {
  return valor === 'es' || valor === 'pt'
}

/** Estados del ciclo KCS para una pregunta sin resolver. */
export type EstadoKcs = 'nueva' | 'revision' | 'cubierta'

/** Claves del conjunto de iconos. Los datos referencian el icono por nombre. */
export type NombreIcono =
  | 'usuario'
  | 'tarjeta'
  | 'paquete'
  | 'devolver'
  | 'escudo'
  | 'documento'
  // Desarrollo (paridad con `IconoCategoria` de `api/app/schemas.py`).
  | 'codigo'
  | 'terminal'
  | 'git'
  | 'base-datos'
  | 'servidor'
  | 'nube'
  | 'api'
  | 'bug'
  | 'llave'
  | 'cpu'
  | 'libro'
  | 'cohete'

export type IdCategoria =
  | 'cuenta'
  | 'pagos'
  | 'envios'
  | 'devoluciones'
  | 'seguridad'
  | 'facturacion'

/**
 * Plantilla visual del sitio público de un portal.
 *
 * `default` es el diseño actual del centro de ayuda y `documentacion` el armazón de
 * documentación (navegación lateral persistente de la base de conocimiento). La
 * resolución tolerante del valor que llega de la API vive en
 * `src/plantillas/plantillas.ts` (`resolverPlantilla`).
 */
export type PlantillaCentroAyuda = 'default' | 'documentacion'

export interface Categoria {
  id: IdCategoria
  /** Segmento de dirección, propio de cada idioma. */
  slug: string
  nombre: string
  /** `null` o ausente = sin icono (la API omite la clave nula en el contenido público). */
  icono?: NombreIcono | null
}

export interface PasoHowTo {
  titulo: string
  descripcion: string
}

export interface PreguntaFrecuente {
  pregunta: string
  respuesta: string
}

export interface BloqueHowTo {
  titulo: string
  pasos: PasoHowTo[]
}

export interface Articulo {
  /** Identificador estable entre idiomas: permite cambiar de idioma sin perder el artículo. */
  id: string
  /** Segmento de dirección, propio de cada idioma. */
  slug: string
  titulo: string
  categoria: IdCategoria
  /** Fecha ISO (AAAA-MM-DD), para el atributo `datetime` de `<time>`. */
  actualizado: string
  minutosLectura: number
  destacado: boolean
  parrafos: string[]
  howTo: BloqueHowTo
  nota?: string
  faq: PreguntaFrecuente[]
  /** Identificadores de artículos relacionados. */
  relacionados: string[]
}

export interface Cita {
  n: number
  titulo: string
  /**
   * Artículo citado. Se guarda el identificador, no la dirección: la dirección
   * depende del idioma activo y la construye el componente. Así la cita siempre
   * resuelve a un artículo que existe.
   */
  articuloId: string
}

/** Fragmento de una respuesta del asistente: texto o marca de cita. */
export type Fragmento =
  | { tipo: 'texto'; texto: string; enfasis?: 'fuerte' | 'cursiva' }
  | { tipo: 'cita'; n: number }

export type MensajeChat =
  | { autor: 'usuario'; texto: string }
  | { autor: 'asistente'; clase: 'saludo'; texto: string }
  | { autor: 'asistente'; clase: 'citado'; fragmentos: Fragmento[]; citas: Cita[] }
  | { autor: 'asistente'; clase: 'sin-resultado'; aviso: string; texto: string }

/**
 * Pregunta sin resolver del ciclo KCS.
 *
 * No forma parte de `ContenidoIdioma`: es texto escrito por las personas usuarias
 * y puede contener datos personales, así que solo se sirve por el endpoint
 * autenticado `/api/admin/preguntas-sin-resolver`. Este tipo sigue describiendo
 * los módulos de `src/data/{es,pt}` que alimentan el seed del backend.
 */
export interface PreguntaSinResolver {
  pregunta: string
  veces: number
  /** Similitud máxima con la base de conocimiento, entre 0 y 1. */
  similitud: number
  /** Fecha ISO (AAAA-MM-DD). */
  fecha: string
  estado: EstadoKcs
}

export interface Metrica {
  clave: 'sinResolver' | 'conCita' | 'creados'
  valor: string
}

/** Contenido público de un idioma. Es lo que sirve `GET /api/{idioma}/contenido`. */
export interface ContenidoIdioma {
  /** Nombre de marca global (campo [Empresa]); reemplaza el placeholder [EMPRESA]. */
  empresa: string
  /** Color de acento de la marca (hex). Alimenta los tokens `--acento*` en SSR. */
  acento: string
  /** Tres paradas del degradado del banner de inicio (hex). */
  bannerDesde: string
  bannerMedio: string
  bannerHasta: string
  /**
   * Plantilla activa del portal. Llega siempre en la respuesta; se resuelve con
   * `resolverPlantilla` (valor desconocido o ausente → `default`) antes de elegir
   * el armazón que se renderiza.
   */
  plantilla: PlantillaCentroAyuda
  /**
   * URL del repositorio de GitHub del portal (solo `https://github.com/…`, lo valida la
   * API). Ausente o `null` = sin enlace: la cabecera de documentación oculta el icono.
   */
  githubUrl?: string | null
  /** Si hay logotipo de marca subido (cabecera y favicon lo usan). */
  logo: boolean
  /**
   * Hash corto de los bytes del logotipo (o `null` sin logo). Se usa como cache-buster
   * en la URL del `<img>` (`/api/marca/logo?v={logoVersion}`) para que al cambiar el
   * logo el navegador vuelva a pedirlo, en vez de reutilizar la copia cacheada.
   */
  logoVersion: string | null
  categorias: Categoria[]
  articulos: Articulo[]
  conversacion: MensajeChat[]
  metricas: Metrica[]
}
