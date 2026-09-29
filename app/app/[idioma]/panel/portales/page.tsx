import { redirect } from 'next/navigation'
import { esIdioma } from '@/types'
import { esSuperAdmin } from '@/auth/nivel'
import { rutas } from '@/i18n/rutas'
import { sesionActual } from '../../../_bff/sesionServidor'
import { PanelI18n } from '../../../_componentes/panel/PanelI18n'
import { GestionPortales } from '../../../_componentes/panel/GestionPortales'

/**
 * Gestión de portales (solo SuperAdmin). Doble guardia en servidor, antes de emitir HTML:
 * sin sesión → login; con sesión de nivel insuficiente → panel. El nivel SuperAdmin se
 * comprueba consultando la sesión al backend (no descodificando el JWT en el borde), que
 * vuelve a autorizar cada operación de todos modos. El SuperAdmin llega aquí por el host
 * de gestión del portal de plataforma.
 */
export default async function PaginaPortales({ params }: { params: Promise<{ idioma: string }> }) {
  const { idioma } = await params
  if (!esIdioma(idioma)) redirect('/es')

  const sesion = await sesionActual()
  if (!sesion) redirect(rutas.login(idioma))
  if (!esSuperAdmin(sesion.nivel)) redirect(rutas.panel(idioma))

  return (
    <PanelI18n idioma={idioma}>
      <GestionPortales idioma={idioma} />
    </PanelI18n>
  )
}
