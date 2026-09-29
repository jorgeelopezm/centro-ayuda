/**
 * Resolución de la pestaña activa del Panel interno a partir del parámetro de la
 * dirección (`?seccion=…`). Es lógica pura —sin red ni componentes— para poder
 * probarla y para concentrar aquí el gating por URL: la pestaña de Administrador
 * nunca se alcanza pidiéndola directamente si la sesión no es Administrador.
 */

export type PestanaId = 'sinResolver' | 'gestion' | 'chats' | 'sugerencias' | 'categorias' | 'admin'

/** Orden en que se muestran las pestañas; la primera es el valor por defecto. */
export const PESTANAS: readonly PestanaId[] = ['sinResolver', 'gestion', 'chats', 'sugerencias', 'categorias', 'admin']

const POR_DEFECTO: PestanaId = 'sinResolver'

function esPestanaId(valor: string | null): valor is PestanaId {
  return (
    valor === 'sinResolver' ||
    valor === 'gestion' ||
    valor === 'chats' ||
    valor === 'sugerencias' ||
    valor === 'categorias' ||
    valor === 'admin'
  )
}

/**
 * Devuelve un `PestanaId` válido:
 * - valor desconocido o ausente → `'sinResolver'`;
 * - `'admin'` sin permiso de Administrador → `'sinResolver'` (no se expone por URL directa);
 * - en el resto, el id solicitado.
 */
export function resolverPestana(param: string | null, puedeAdministrar: boolean): PestanaId {
  if (!esPestanaId(param)) return POR_DEFECTO
  if (param === 'admin' && !puedeAdministrar) return POR_DEFECTO
  return param
}
