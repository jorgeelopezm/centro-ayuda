import { redirect } from 'next/navigation'
import { esIdioma } from '@/types'
import { esAdministrador } from '@/auth/nivel'
import { rutas } from '@/i18n/rutas'
import { sesionActual } from '../../../_bff/sesionServidor'
import { PanelI18n } from '../../../_componentes/panel/PanelI18n'
import { GestionDocumentos } from '../../../_componentes/panel/GestionDocumentos'

/**
 * Gestión de documentos del índice RAG (solo Administrador). Doble guardia en
 * servidor: sin sesión → login; sesión de nivel insuficiente → panel. El nivel
 * Administrador se comprueba consultando la sesión al backend, no descodificando
 * el JWT en el borde.
 */
export default async function PaginaDocumentos({ params }: { params: Promise<{ idioma: string }> }) {
  const { idioma } = await params
  if (!esIdioma(idioma)) redirect('/es')

  const sesion = await sesionActual()
  if (!sesion) redirect(rutas.login(idioma))
  if (!esAdministrador(sesion.nivel)) redirect(rutas.panel(idioma))

  return (
    <PanelI18n idioma={idioma}>
      <GestionDocumentos idioma={idioma} />
    </PanelI18n>
  )
}
