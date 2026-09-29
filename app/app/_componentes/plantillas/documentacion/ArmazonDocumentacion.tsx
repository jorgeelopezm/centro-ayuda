'use client'

import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
import type { ContenidoIdioma, Idioma } from '@/types'
import { derivarTokensAcento, derivarTokensAcentoNoche } from '@/seguridad/contraste'
import { alternarTema, cookieTema, esOscuro, type Tema } from '@/tema/tema'
import { CabeceraDocumentacion } from './CabeceraDocumentacion'
import { NavegacionConocimiento } from './NavegacionConocimiento'

/**
 * Armazón de la plantilla de documentación: cabecera, barra lateral de la base de
 * conocimiento y columna de contenido. Reproduce la geometría de la referencia
 * (`docs/design/devdocs_layout.html`): barra superior, barra lateral persistente y columna
 * de contenido con su propio desplazamiento, en vez del banner del inicio predeterminado.
 *
 * Es Client Component para compartir entre la cabecera y la barra lateral el estado del
 * panel deslizante en pantalla estrecha y el del **modo noche**; `children` son las
 * páginas del servidor, que siguen renderizándose en servidor y llegan en el HTML inicial
 * (incluida la navegación completa, al ser `NavegacionConocimiento` prerenderizable).
 *
 * Modo noche: `data-tema` en la raíz activa el mapa de colores de `index.css`, y el
 * atributo `style` fija el acento con `light-dark()` (el de marca en claro, el derivado
 * por `derivarTokensAcentoNoche` en oscuro). El tema inicial llega de la cookie leída en
 * servidor, así que no hay parpadeo; con `sistema` lo resuelve el propio CSS.
 *
 * El pie de página no vive aquí: es específico de cada página (`PieDocumentacion` cierra la
 * columna de contenido y, en el artículo, muestra su última actualización), así que lo
 * renderiza cada página dentro de su `<main id="main-content">`.
 */
export function ArmazonDocumentacion({
  idioma,
  contenido,
  temaInicial,
  children,
}: {
  idioma: Idioma
  contenido: ContenidoIdioma
  temaInicial: Tema
  children: ReactNode
}) {
  const [navAbierta, setNavAbierta] = useState(false)
  const [tema, setTema] = useState<Tema>(temaInicial)
  // Preferencia del sistema, solo para saber qué se ve con `sistema` (estado del botón);
  // el color en sí ya lo decide el CSS. En servidor se asume claro: el botón se corrige
  // al montar sin afectar al HTML, que es el mismo en ambos casos.
  const [sistemaOscuro, setSistemaOscuro] = useState(false)

  useEffect(() => {
    const consulta = window.matchMedia('(prefers-color-scheme: dark)')
    setSistemaOscuro(consulta.matches)
    const alCambiar = (e: MediaQueryListEvent) => setSistemaOscuro(e.matches)
    consulta.addEventListener('change', alCambiar)
    return () => consulta.removeEventListener('change', alCambiar)
  }, [])

  const oscuro = esOscuro(tema, sistemaOscuro)

  function alternar() {
    const siguiente = alternarTema(oscuro)
    setTema(siguiente)
    document.cookie = cookieTema(siguiente, window.location.protocol === 'https:')
  }

  // `contenido.acento` ya es hex validado (el servidor lo valida al guardar y
  // `derivarTokensAcento` lanza con cualquier otra cosa), así que interpolarlo en el
  // estilo no abre inyección de CSS.
  const estiloAcento = useMemo(() => {
    const dia = derivarTokensAcento(contenido.acento)
    const noche = derivarTokensAcentoNoche(contenido.acento)
    return {
      '--acento': `light-dark(${contenido.acento}, ${noche.acento})`,
      '--acento-hover': `light-dark(${dia.hover}, ${noche.hover})`,
      '--acento-claro': `light-dark(${dia.claro}, ${noche.claro})`,
      '--acento-foco': `light-dark(${dia.foco}, ${noche.foco})`,
    } as CSSProperties
  }, [contenido.acento])

  return (
    <div
      data-tema={tema}
      style={estiloAcento}
      className="flex flex-col bg-white min-h-screen lg:h-screen lg:overflow-hidden"
    >
      <CabeceraDocumentacion
        idioma={idioma}
        contenido={contenido}
        navAbierta={navAbierta}
        onAlternarNav={() => setNavAbierta(v => !v)}
        oscuro={oscuro}
        onAlternarTema={alternar}
      />
      <div className="flex flex-1 min-h-0">
        <NavegacionConocimiento
          idioma={idioma}
          contenido={contenido}
          abierta={navAbierta}
          onCerrar={() => setNavAbierta(false)}
        />
        <div className="flex-1 min-w-0 lg:h-full lg:overflow-y-auto">{children}</div>
      </div>
    </div>
  )
}
