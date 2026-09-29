import { redirect } from 'next/navigation'
import { esIdioma } from '@/types'
import { rutas } from '@/i18n/rutas'
import { cargarContenidoServidor } from '@/data/servidor'
import { sesionActual } from '../../_bff/sesionServidor'
import { PanelI18n } from '../../_componentes/panel/PanelI18n'
import { PanelInterno } from '../../_componentes/panel/PanelInterno'

/**
 * Panel interno. La guardia se resuelve en servidor antes de emitir HTML: sin
 * sesión válida (el `middleware` ya renovó si podía) se redirige a login. El
 * nivel se obtiene de la sesión y se pasa al panel (Administrador añade la pestaña de
 * administración; el backend vuelve a autorizar cada operación).
 */
export default async function PaginaPanel({ params }: { params: Promise<{ idioma: string }> }) {
  const { idioma } = await params
  if (!esIdioma(idioma)) redirect('/es')

  const sesion = await sesionActual()
  if (!sesion) redirect(rutas.login(idioma))

  const contenido = await cargarContenidoServidor(idioma)

  return (
    <PanelI18n idioma={idioma}>
      <PanelInterno idioma={idioma} nivel={sesion.nivel} contenido={contenido} />
    </PanelI18n>
  )
}
