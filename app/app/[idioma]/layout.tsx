import type { CSSProperties, ReactNode } from 'react'
import type { Metadata } from 'next'
import { DM_Sans, DM_Serif_Display } from 'next/font/google'
import { redirect } from 'next/navigation'
import { cookies } from 'next/headers'
import { esIdioma, type ContenidoIdioma } from '@/types'
import { cargarContenidoServidor, ErrorPortal, type MotivoPortal } from '@/data/servidor'
import { derivarTokensAcento } from '@/seguridad/contraste'
import { COOKIE_TEMA, resolverTema } from '@/tema/tema'
import '../globals.css'
import { SkipLink } from '../_componentes/SkipLink'
import { ChatLanzador } from '../_componentes/ChatLanzador'
import { EstadoPortal } from '../_componentes/EstadoPortal'
import { CromoPorPlantilla } from '../_componentes/CromoPorPlantilla'

// Fuentes de marca autoalojadas por Next (`next/font`): se descargan en la
// compilación y se sirven desde el mismo origen, así la CSP estricta
// (`font-src 'self'`) las permite sin abrir a Google Fonts. Cada una expone una
// variable CSS que consume el CSS base (`--font-sans`) y los títulos (`--font-serif`).
const fuenteSans = DM_Sans({ subsets: ['latin'], variable: '--font-sans', display: 'swap' })
const fuenteSerif = DM_Serif_Display({
  subsets: ['latin'],
  weight: '400',
  variable: '--font-serif',
  display: 'swap',
})

/** Prerenderiza los idiomas soportados en la compilación. */
export function generateStaticParams() {
  return [{ idioma: 'es' }, { idioma: 'pt' }]
}

/**
 * Favicon dinámico: si hay logotipo subido, apunta a `/api/marca/logo` (mismo
 * origen, compatible con la CSP `img-src 'self'`). Sin logo, se omite y el
 * navegador cae al favicon por defecto.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ idioma: string }>
}): Promise<Metadata> {
  const { idioma } = await params
  let hayLogo = false
  let logoVersion: string | null = null
  try {
    const contenido = await cargarContenidoServidor(esIdioma(idioma) ? idioma : 'es')
    hayLogo = contenido.logo
    logoVersion = contenido.logoVersion
  } catch {
    hayLogo = false
  }
  // Cache-buster en el favicon: al cambiar el logo el navegador vuelve a pedirlo
  // en vez de reutilizar la copia cacheada de la URL anterior.
  const iconoUrl = logoVersion ? `/api/marca/logo?v=${logoVersion}` : '/api/marca/logo'
  return {
    title: 'Centro de Ayuda',
    icons: hayLogo ? { icon: iconoUrl } : undefined,
  }
}

/**
 * Tokens de acento y banner inyectados inline desde la paleta servida, para que
 * lleguen en el HTML inicial (sin parpadeo) y sobrescriban los valores por defecto
 * de `index.css`. Se usa un atributo `style` (no un `<style>`): la CSP lo permite
 * sin `nonce`. Los tokens derivados (hover/claro/foco) se calculan igual que en el
 * servidor de la API, garantizando la misma escala que se validó por contraste.
 */
function estiloMarca(contenido: ContenidoIdioma | null): CSSProperties | undefined {
  if (!contenido) return undefined
  const tokens = derivarTokensAcento(contenido.acento)
  return {
    '--acento': contenido.acento,
    '--acento-hover': tokens.hover,
    '--acento-claro': tokens.claro,
    '--acento-foco': tokens.foco,
    '--banner-desde': contenido.bannerDesde,
    '--banner-medio': contenido.bannerMedio,
    '--banner-hasta': contenido.bannerHasta,
  } as CSSProperties
}

/**
 * Layout raíz por idioma. Es el layout más externo (no hay `app/layout.tsx`):
 * fija `<html lang>` con el idioma del primer segmento, resuelto en servidor.
 * Un idioma no soportado se redirige a `es` antes de emitir HTML.
 */
export default async function LayoutIdioma({
  children,
  params,
}: {
  children: ReactNode
  params: Promise<{ idioma: string }>
}) {
  const { idioma } = await params
  if (!esIdioma(idioma)) redirect('/es')

  // Solo el idioma activo. La cabecera necesita el nombre de empresa y el chat
  // la conversación de ejemplo; ambos salen de este único contenido. Se distinguen
  // dos fallos: si el host no resuelve un portal (`ErrorPortal`) se muestra el estado
  // accesible de portal (task 3.4), sin cabecera ni marca de ningún otro portal; un
  // fallo genérico de la fuente cae en `null` y lo comunica `error.tsx` (task 3.5).
  let contenido: ContenidoIdioma | null = null
  let motivoPortal: MotivoPortal | null = null
  try {
    contenido = await cargarContenidoServidor(idioma)
  } catch (e) {
    if (e instanceof ErrorPortal) motivoPortal = e.motivo
  }

  // Preferencia de modo noche (solo la usa la plantilla de documentación). Se lee aquí,
  // en servidor, para que el HTML inicial salga ya con el tema elegido, sin parpadeo.
  const tema = resolverTema((await cookies()).get(COOKIE_TEMA)?.value)

  // La plantilla activa la resuelve `CromoPorPlantilla` (que además deja fuera de ella la
  // superficie de administración), no el layout: aquí solo se decide el cromo.

  return (
    <html
      lang={idioma}
      className={`${fuenteSans.variable} ${fuenteSerif.variable}`}
      style={estiloMarca(contenido)}
    >
      <body>
        {/* id="root": el `Modal` del panel marca este contenedor como inert
            mientras está abierto (el diálogo vive fuera, en un portal a body). */}
        <div id="root" className="min-h-screen bg-slate-50">
          {motivoPortal ? (
            <EstadoPortal idioma={idioma} motivo={motivoPortal} />
          ) : (
            <>
              <SkipLink idioma={idioma} />
              {/* El cromo lo elige `CromoPorPlantilla`: con `documentacion` monta el
                  armazón (cabecera + barra lateral persistente + columna de contenido) y
                  con `default` o en la superficie de administración, la cabecera de
                  siempre. El `ChatLanzador` se mantiene en las dos: la plantilla es
                  presentación, no una pérdida de funciones. */}
              <CromoPorPlantilla idioma={idioma} contenido={contenido} tema={tema}>
                {children}
              </CromoPorPlantilla>
              {contenido && <ChatLanzador idioma={idioma} />}
            </>
          )}
        </div>
      </body>
    </html>
  )
}
