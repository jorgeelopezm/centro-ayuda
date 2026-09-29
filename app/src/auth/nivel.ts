/**
 * Niveles de acceso jerárquicos (espejo de `NivelAcceso` en el backend).
 *
 * El valor entero ordena la herencia de permisos: autorizar es comparar
 * `nivel_actual >= nivel_requerido`. La interfaz usa esto para ocultar los
 * controles de Administrador, pero la autoridad siempre es el backend.
 */

export const NivelAcceso = {
  ANONIMO: 1,
  EDITOR: 2,
  ADMINISTRADOR: 3,
  SUPERADMIN: 4,
} as const

export type NivelAcceso = (typeof NivelAcceso)[keyof typeof NivelAcceso]

/**
 * ¿La sesión de nivel `actual` alcanza el nivel `requerido`? Sin sesión
 * (`null`/`undefined`) es Anonymous y no alcanza ningún recurso de administración.
 * Función pura: se comprueba sin red ni componentes.
 */
export function tieneNivel(actual: number | null | undefined, requerido: NivelAcceso): boolean {
  return actual != null && actual >= requerido
}

export function esAdministrador(nivel: number | null | undefined): boolean {
  return tieneNivel(nivel, NivelAcceso.ADMINISTRADOR)
}

/**
 * ¿La sesión es de un SuperAdmin (nivel 4, transversal a los portales)? El SuperAdmin
 * gestiona portales; no se ata a un portal de contenido. La autoridad sigue siendo el
 * backend: esto solo decide qué controles muestra la interfaz.
 */
export function esSuperAdmin(nivel: number | null | undefined): boolean {
  return tieneNivel(nivel, NivelAcceso.SUPERADMIN)
}
