import { redirect } from 'next/navigation'
import { esIdioma } from '@/types'
import { rutas } from '@/i18n/rutas'
import { sesionActual } from '../../_bff/sesionServidor'
import { FormularioLogin } from '../../_componentes/panel/FormularioLogin'

/** Inicio de sesión. Si ya hay sesión válida, va directo al panel. */
export default async function PaginaLogin({ params }: { params: Promise<{ idioma: string }> }) {
  const { idioma } = await params
  if (!esIdioma(idioma)) redirect('/es')

  const sesion = await sesionActual()
  if (sesion) redirect(rutas.panel(idioma))

  return <FormularioLogin idioma={idioma} />
}
