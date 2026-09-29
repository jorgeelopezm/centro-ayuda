import { redirect } from 'next/navigation'
import { esIdioma } from '@/types'
import { rutas } from '@/i18n/rutas'

/**
 * Entrada al panel interno. La cabecera pública ya no enlaza el panel, así que el acceso
 * de administración es esta dirección conocida (`/es/panel-interno`, `/pt/painel-interno`).
 *
 * Solo redirige a `/{idioma}/panel`: la guardia del borde (`proxy.ts`) decide allí, sin
 * duplicar lógica, entre mostrar el login (sin sesión) o el panel (con sesión válida).
 * No es un control de acceso: la autorización sigue en el servidor.
 */
export default async function PaginaPanelInterno({
  params,
}: {
  params: Promise<{ idioma: string }>
}) {
  const { idioma } = await params
  redirect(rutas.panel(esIdioma(idioma) ? idioma : 'es'))
}
