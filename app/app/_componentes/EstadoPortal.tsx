import type { Idioma } from '@/types'
import type { MotivoPortal } from '@/data/servidor'
import { traducir } from '@/i18n/traducir'
import { Ic } from '@/components/iconos'

/**
 * Estado accesible cuando el host no corresponde a un portal servible (task 3.4):
 * `no-encontrado` (host desconocido, 404) o `no-disponible` (portal suspendido, 503).
 *
 * Se renderiza en el servidor, en lugar del contenido, para no filtrar jamás datos ni
 * marca de otro portal: sin portal resuelto no hay cabecera, chat ni acento propios.
 * Es un componente de servidor (recibe `idioma` y `motivo` por props, sin hooks de
 * cliente); el idioma llega ya resuelto del primer segmento de la ruta.
 */
export function EstadoPortal({ idioma, motivo }: { idioma: Idioma; motivo: MotivoPortal }) {
  const t = traducir(idioma)
  const clave = motivo === 'no-encontrado' ? 'noEncontrado' : 'noDisponible'

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="min-h-screen flex items-center justify-center bg-slate-50 px-4 focus:outline-none"
    >
      <div role="alert" className="max-w-md w-full rounded-2xl border border-slate-200 bg-white p-6 text-center">
        <div className="mx-auto w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-4">
          <Ic.AlertCircle size={24} className="text-slate-700" />
        </div>
        <h1 className="text-lg font-bold text-slate-900 mb-1">{t(`portal.${clave}Titulo`)}</h1>
        <p className="text-sm text-slate-600">{t(`portal.${clave}Ayuda`)}</p>
      </div>
    </main>
  )
}
