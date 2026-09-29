/**
 * Punto único de acceso a la API de administración (`/api/admin/*`).
 *
 * Espeja lo que `index.ts` hace con el contenido público: las direcciones, los
 * métodos y la forma del cuerpo viven aquí y no repartidos entre el panel y el
 * formulario de artículos. Las funciones devuelven la `Response` sin
 * interpretar, porque cada pantalla reacciona distinto a cada código: el panel
 * lleva al login ante un 401 y el formulario distingue el 409 del identificador
 * duplicado.
 */

import { apiFetch } from '@/bff/apiFetch'
import type { EstadoKcs, Idioma, NombreIcono, PlantillaCentroAyuda } from '@/types'

/** Forma del artículo con sus dos idiomas que devuelve/acepta la API admin. */
export interface TraduccionAdmin {
  slug: string
  titulo: string
  parrafos: string[]
  howTo: { titulo: string; pasos: { titulo: string; descripcion: string }[] }
  nota: string | null
  faq: { pregunta: string; respuesta: string }[]
}
export interface ArticuloAdmin {
  id: string
  categoria: string
  actualizado: string
  minutosLectura: number
  destacado: boolean
  relacionados: string[]
  es: TraduccionAdmin
  pt: TraduccionAdmin
}

/** Fila de la tabla de preguntas sin resolver del panel interno. */
export interface PreguntaAdmin {
  id: number
  idioma: string
  pregunta: string
  veces: number
  similitud: number
  fecha: string
  estado: EstadoKcs
}

export function listarPreguntas(idioma: Idioma): Promise<Response> {
  return apiFetch(`/api/admin/preguntas-sin-resolver?idioma=${idioma}`)
}

export function obtenerArticulo(id: string): Promise<Response> {
  return apiFetch(`/api/admin/articulos/${id}`)
}

export function eliminarArticulo(id: string): Promise<Response> {
  return apiFetch(`/api/admin/articulos/${id}`, { method: 'DELETE' })
}

/** A dónde va un guardado: artículo nuevo, edición, alta desde pregunta o desde sugerencia de IA. */
export type DestinoArticulo =
  | { tipo: 'crear' }
  | { tipo: 'editar'; articuloId: string }
  | { tipo: 'desdePregunta'; preguntaId: number }
  | { tipo: 'desdeSugerencia'; sugerenciaId: string }

/**
 * Dirección, método y cuerpo de un guardado. Función pura: no toca la red, así
 * que la decisión se puede comprobar por separado del componente.
 */
export function peticionGuardado(
  payload: ArticuloAdmin,
  destino: DestinoArticulo,
): { url: string; metodo: string; cuerpo: unknown } {
  if (destino.tipo === 'desdePregunta') {
    return {
      url: `/api/admin/preguntas-sin-resolver/${destino.preguntaId}/crear-articulo`,
      metodo: 'POST',
      cuerpo: payload,
    }
  }
  if (destino.tipo === 'desdeSugerencia') {
    // "Aceptar" reutiliza el alta de artículo (bilingüe atómico + re-indexado)
    // con el contenido editado por la persona revisora; marca la sugerencia
    // `aceptada` en el mismo commit (`admin_sugerencias.aceptar`).
    return {
      url: `/api/admin/sugerencias/${encodeURIComponent(destino.sugerenciaId)}/aceptar`,
      metodo: 'POST',
      cuerpo: payload,
    }
  }
  if (destino.tipo === 'crear') {
    return { url: '/api/admin/articulos', metodo: 'POST', cuerpo: payload }
  }
  // El id va en la dirección; la API de actualización lo rechaza en el cuerpo.
  const { id: _id, ...sinId } = payload
  return { url: `/api/admin/articulos/${destino.articuloId}`, metodo: 'PUT', cuerpo: sinId }
}

export function guardarArticulo(payload: ArticuloAdmin, destino: DestinoArticulo): Promise<Response> {
  const { url, metodo, cuerpo } = peticionGuardado(payload, destino)
  return apiFetch(url, { method: metodo, body: JSON.stringify(cuerpo) })
}

// ── Gestión de categorías (Editor + Administrador) ──────────────────────────

/** Traducción de una categoría (nombre + slug por idioma). */
export interface TraduccionCategoriaAdmin {
  slug: string
  nombre: string
}

/** Categoría con sus dos idiomas que devuelve/acepta la API admin. */
export interface CategoriaAdmin {
  id: string
  /** `null` = sin icono. */
  icono: NombreIcono | null
  orden: number
  es: TraduccionCategoriaAdmin
  pt: TraduccionCategoriaAdmin
}

export function listarCategorias(): Promise<Response> {
  return apiFetch('/api/admin/categorias')
}

/** A dónde va un guardado de categoría: alta o edición. */
export type DestinoCategoria = { tipo: 'crear' } | { tipo: 'editar'; categoriaId: string }

/**
 * Dirección, método y cuerpo de un guardado de categoría. Función pura (no toca
 * la red): al crear va el payload completo; al editar, el id viaja en la
 * dirección y la API lo rechaza en el cuerpo. Espeja `peticionGuardado`.
 */
export function peticionCategoria(
  payload: CategoriaAdmin,
  destino: DestinoCategoria,
): { url: string; metodo: string; cuerpo: unknown } {
  if (destino.tipo === 'crear') {
    return { url: '/api/admin/categorias', metodo: 'POST', cuerpo: payload }
  }
  const { id: _id, ...sinId } = payload
  return { url: `/api/admin/categorias/${destino.categoriaId}`, metodo: 'PUT', cuerpo: sinId }
}

export function guardarCategoria(payload: CategoriaAdmin, destino: DestinoCategoria): Promise<Response> {
  const { url, metodo, cuerpo } = peticionCategoria(payload, destino)
  return apiFetch(url, { method: metodo, body: JSON.stringify(cuerpo) })
}

export function eliminarCategoria(id: string): Promise<Response> {
  return apiFetch(`/api/admin/categorias/${id}`, { method: 'DELETE' })
}

// ── Sesión: identidad y nivel de acceso ─────────────────────────────────────

/** Identidad de la sesión actual, que devuelve `GET /api/auth/me`. */
export interface SesionAdmin {
  email: string
  nivel: number
}

export function obtenerSesion(): Promise<Response> {
  return apiFetch('/api/auth/me')
}

// ── Gestión de usuarios (solo Administrador) ────────────────────────────────

/** Usuario administrable que devuelve `/api/admin/usuarios`. Sin el hash. */
export interface UsuarioAdmin {
  id: number
  email: string
  nivel: number
  activo: boolean
  creado: string
}

/** Datos de un usuario que se crean o editan desde el formulario. */
export interface UsuarioPayload {
  email: string
  nivel: number
  /** Obligatoria al crear; opcional al editar (vacía = no cambiar). */
  password?: string
}

export function listarUsuarios(): Promise<Response> {
  return apiFetch('/api/admin/usuarios')
}

/** A dónde va un guardado de usuario: alta o edición. */
export type DestinoUsuario = { tipo: 'crear' } | { tipo: 'editar'; usuarioId: number }

/**
 * Dirección, método y cuerpo de un guardado de usuario. Función pura (no toca la
 * red): al crear, la contraseña es obligatoria; al editar, solo viaja si se
 * escribió una nueva. Espeja `peticionGuardado` para artículos.
 */
export function peticionUsuario(
  payload: UsuarioPayload,
  destino: DestinoUsuario,
): { url: string; metodo: string; cuerpo: unknown } {
  if (destino.tipo === 'crear') {
    return {
      url: '/api/admin/usuarios',
      metodo: 'POST',
      cuerpo: { email: payload.email, nivel: payload.nivel, password: payload.password },
    }
  }
  // Al editar, una contraseña vacía no viaja: significa "no cambiarla".
  const cuerpo: Record<string, unknown> = { email: payload.email, nivel: payload.nivel }
  if (payload.password) cuerpo.password = payload.password
  return { url: `/api/admin/usuarios/${destino.usuarioId}`, metodo: 'PUT', cuerpo }
}

export function guardarUsuario(payload: UsuarioPayload, destino: DestinoUsuario): Promise<Response> {
  const { url, metodo, cuerpo } = peticionUsuario(payload, destino)
  return apiFetch(url, { method: metodo, body: JSON.stringify(cuerpo) })
}

export function activarUsuario(id: number): Promise<Response> {
  return apiFetch(`/api/admin/usuarios/${id}/activar`, { method: 'POST' })
}

export function desactivarUsuario(id: number): Promise<Response> {
  return apiFetch(`/api/admin/usuarios/${id}/desactivar`, { method: 'POST' })
}

// ── Gestión de portales (solo SuperAdmin) ───────────────────────────────────

/** Portal que devuelve `/api/admin/portales`, para el listado del SuperAdmin. */
export interface PortalAdmin {
  id: string
  slug: string
  nombreEmpresa: string
  estado: string
  /** Host principal (subdominio) del portal, o null si aún no lo tiene. */
  host: string | null
  creado: string
  /** Correo del Administrador inicial del portal, o null en el caso límite de que no tenga ninguno. */
  adminEmail: string | null
}

/** Datos de alta de un portal: sus atributos y su Administrador inicial. */
export interface PortalPayload {
  slug: string
  nombreEmpresa: string
  adminEmail: string
  adminPassword: string
}

export function listarPortales(): Promise<Response> {
  return apiFetch('/api/admin/portales')
}

export function crearPortal(payload: PortalPayload): Promise<Response> {
  return apiFetch('/api/admin/portales', { method: 'POST', body: JSON.stringify(payload) })
}

export function suspenderPortal(id: string): Promise<Response> {
  return apiFetch(`/api/admin/portales/${encodeURIComponent(id)}/suspender`, { method: 'POST' })
}

export function reactivarPortal(id: string): Promise<Response> {
  return apiFetch(`/api/admin/portales/${encodeURIComponent(id)}/reactivar`, { method: 'POST' })
}

// ── Campo [Empresa] (solo Administrador) ────────────────────────────────────

export function guardarEmpresa(empresa: string): Promise<Response> {
  return apiFetch('/api/admin/ajustes/empresa', {
    method: 'PUT',
    body: JSON.stringify({ empresa }),
  })
}

// ── Marca visual: paleta y logotipo (solo Administrador) ────────────────────

/**
 * Paleta editable: solo el acento. El degradado del banner ya no se elige a mano; lo
 * deriva el servidor del acento (`derivar_degradado_banner`), accesible por construcción.
 */
export interface MarcaPayload {
  acento: string
}

/**
 * Guarda la paleta (solo el acento). El servidor deriva el banner y valida el contraste
 * WCAG; responde 422 con el par que falla si no cumple, y la pantalla distingue ese
 * código para avisar sin persistir.
 */
export function guardarMarca(payload: MarcaPayload): Promise<Response> {
  return apiFetch('/api/admin/ajustes/marca', { method: 'PUT', body: JSON.stringify(payload) })
}

/**
 * Sube el logotipo como cuerpo binario crudo (PNG/ICO/JPEG). Se fija el `Content-Type`
 * explícito para que `apiFetch` no lo trate como JSON; el servidor decide el tipo
 * real por magic bytes, no por esta cabecera.
 */
export function subirLogo(archivo: File): Promise<Response> {
  return apiFetch('/api/admin/ajustes/logo', {
    method: 'POST',
    body: archivo,
    headers: { 'Content-Type': archivo.type || 'application/octet-stream' },
  })
}

// ── Plantilla del centro de ayuda (solo Administrador) ──────────────────────

/**
 * Guarda la plantilla del sitio público del portal. El servidor valida el valor contra el
 * conjunto admitido (422 si no lo es) y responde con el valor guardado, que es la verdad
 * que el panel muestra como activa.
 */
export function guardarPlantilla(plantilla: PlantillaCentroAyuda): Promise<Response> {
  return apiFetch('/api/admin/ajustes/plantilla', {
    method: 'PUT',
    body: JSON.stringify({ plantilla }),
  })
}

// ── Enlace de GitHub del portal (solo Administrador) ────────────────────────

/**
 * Guarda el enlace de GitHub del portal; cadena vacía lo borra (oculta el icono). El
 * servidor solo admite `https://github.com/…` (422 en otro caso) y responde con el valor
 * guardado (`{ url }`), que es lo que el panel muestra.
 */
export function guardarGithub(url: string): Promise<Response> {
  return apiFetch('/api/admin/ajustes/github', {
    method: 'PUT',
    body: JSON.stringify({ url }),
  })
}

// ── Gestión de documentos (RAG, solo Administrador) ─────────────────────────

/** Estado de la ingesta de un documento. Coincide con el enum del backend. */
export type EstadoDocumento = 'pendiente' | 'procesando' | 'listo' | 'error'

/** Documento devuelto por el backend. NUNCA lleva binario ni embeddings. */
export interface DocumentoAdmin {
  id: number
  nombre: string
  mime: string
  idioma: 'es' | 'pt' | 'ambos'
  estado: EstadoDocumento
  errorDetalle: string | null
  bytes: number
  creado: string
  actualizado: string
}

export function listarDocumentos(): Promise<Response> {
  return apiFetch('/api/admin/documentos')
}

/**
 * Consulta el estado de un documento. Se usa para hacer polling mientras la
 * ingesta está en `procesando` (el POST responde antes de terminar).
 */
export function estadoDocumento(id: number): Promise<Response> {
  return apiFetch(`/api/admin/documentos/${id}`)
}

/**
 * Sube un documento como cuerpo binario crudo (patrón `subirLogo`). Se fija el
 * `Content-Type` explícito para que `apiFetch` no lo trate como JSON; el nombre
 * viaja en `Content-Disposition` para que el servidor lo guarde tal cual, y el
 * idioma como query param.
 */
export function subirDocumento(archivo: File, idioma: 'es' | 'pt' | 'ambos' = 'ambos'): Promise<Response> {
  const nombreCodificado = encodeURIComponent(archivo.name)
  return apiFetch(`/api/admin/documentos?idioma=${idioma}`, {
    method: 'POST',
    body: archivo,
    headers: {
      'Content-Type': archivo.type || 'application/octet-stream',
      'Content-Disposition': `attachment; filename*=UTF-8''${nombreCodificado}`,
    },
  })
}

export function eliminarDocumento(id: number): Promise<Response> {
  return apiFetch(`/api/admin/documentos/${id}`, { method: 'DELETE' })
}

// ── Traducción asistida por IA ──────────────────────────────────────────────

/**
 * Pide al backend traducir el contenido de un idioma al otro. Devuelve la
 * `Response` sin interpretar: el formulario distingue el 409 (proveedor sin
 * configurar) del resto de errores. No persiste nada; el resultado es un borrador.
 */
export function traducirArticulo(origen: Idioma, contenido: TraduccionAdmin): Promise<Response> {
  return apiFetch('/api/admin/articulos/traducir', {
    method: 'POST',
    body: JSON.stringify({ origen, contenido }),
  })
}

/**
 * Pide al backend traducir el nombre (y slug) de una categoría de un idioma al
 * otro. Espejo de `traducirArticulo`, acotado al contenido de categoría.
 */
export function traducirCategoria(
  origen: Idioma,
  contenido: TraduccionCategoriaAdmin,
): Promise<Response> {
  return apiFetch('/api/admin/categorias/traducir', {
    method: 'POST',
    body: JSON.stringify({ origen, contenido }),
  })
}

// ── Configuración de proveedor de IA (solo SuperAdmin) ──────────────────────

/** Roles de IA independientes: chat, traducción y embeddings del RAG. */
export type RolIA = 'chat' | 'traduccion' | 'embeddings'

/**
 * Estado de un proveedor: si tiene clave configurada y una pista (los últimos
 * caracteres) para identificarla. Nunca incluye la clave completa.
 */
export interface ProveedorEstado {
  id: string
  configurada: boolean
  /** Últimos caracteres de la clave (p. ej. "s7xq"), o null si no hay/es corta. */
  pista?: string | null
}

/**
 * Proveedores con motor real por rol. El backend rechaza con 422 cualquier
 * asignación de rol → proveedor fuera de estas listas; la UI filtra sus
 * selectores con este mapa.
 */
export interface RolesSoportados {
  chat: string[]
  traduccion: string[]
  embeddings: string[]
}

/**
 * Configuración de IA que devuelve `GET /api/admin/config-ia`. Sin claves.
 * `proveedorX = null` significa «sin proveedor asignado para ese rol»: la fábrica
 * del rol cae al default codificado en el backend.
 */
export interface ConfigIAAdmin {
  proveedorChat: string | null
  proveedorTraduccion: string | null
  proveedorEmbeddings: string | null
  proveedores: ProveedorEstado[]
  rolesSoportados: RolesSoportados
}

/**
 * Datos que se envían al guardar la configuración. Todos los campos son
 * opcionales; los que llegan sobrescriben, los que no, se dejan como están.
 *
 * - `proveedorX = null | ausente` → no cambiar ese rol.
 * - `clave` vacía/ausente → no cambiar la clave (requiere `proveedor` si viene).
 * - `borrarClave: true` con `proveedor` → borrar esa fila de `config_ia_clave`.
 *   El backend responde 409 si el proveedor está en uso por algún rol.
 */
export interface ConfigIAPayload {
  proveedorChat?: string
  proveedorTraduccion?: string
  proveedorEmbeddings?: string
  proveedor?: string
  clave?: string
  borrarClave?: boolean
}

export function obtenerConfigIA(): Promise<Response> {
  return apiFetch('/api/admin/config-ia')
}

export function guardarConfigIA(payload: ConfigIAPayload): Promise<Response> {
  return apiFetch('/api/admin/config-ia', { method: 'PUT', body: JSON.stringify(payload) })
}

/**
 * Estado de un rol tras sondear su proveedor (`GET /api/admin/config-ia/salud`).
 *
 * `credenciales` (clave revocada) y `saldo` (cuenta sin fondos) se distinguen a
 * propósito: los dos se ven como un 502 genérico en el panel, pero uno se arregla
 * rotando la clave y el otro recargando la cuenta.
 */
export type EstadoSaludIA = 'ok' | 'sin_clave' | 'credenciales' | 'saldo' | 'timeout' | 'error'

export interface SaludRolIA {
  rol: 'chat' | 'traduccion' | 'embeddings'
  proveedor: string
  estado: EstadoSaludIA
  /** Texto redactado por el backend; nunca el mensaje crudo del proveedor. */
  detalle: string
  comprobadoEn: string
}

export interface SaludIA {
  roles: SaludRolIA[]
}

/**
 * Sondea los tres roles contra sus proveedores. Hace llamadas salientes reales,
 * así que se invoca **bajo demanda** (botón «Comprobar»), nunca al montar el panel.
 */
export function comprobarSaludIA(): Promise<Response> {
  return apiFetch('/api/admin/config-ia/salud')
}
