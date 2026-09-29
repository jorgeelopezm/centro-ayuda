'use client'

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Modal } from '@/components/Modal'
import { Ic } from '@/components/iconos'
import {
  obtenerChat,
  type ChatDetalle,
  type ChatInteraccion,
} from '@/data/adminChats'
import { VeredictoChip } from './VeredictoChip'

/**
 * Modal con el hilo completo por `turno` de un `chat_id`. Reusa el `Modal`
 * accesible (foco atrapado + Esc + retorno de foco al disparador) y pide el
 * detalle al BFF (`/api/admin/chats/{chat_id}`), que reenvía al backend con la
 * cookie. Cada turno muestra consulta, veredicto, respuesta y citas.
 */
export function DetalleChatModal({
  chatId,
  onCerrar,
  onSesionExpirada,
}: {
  chatId: string
  onCerrar: () => void
  onSesionExpirada: () => void
}) {
  const { t, i18n } = useTranslation()
  const [detalle, setDetalle] = useState<ChatDetalle | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    let cancelado = false
    setCargando(true)
    setError(null)
    obtenerChat(chatId)
      .then(async resp => {
        if (cancelado) return
        if (resp.ok) {
          setDetalle((await resp.json()) as ChatDetalle)
        } else if (resp.status === 401) {
          onSesionExpirada()
        } else {
          setError(t('panelChats.errorDetalle'))
        }
      })
      .catch(() => {
        if (!cancelado) setError(t('panelChats.errorDetalle'))
      })
      .finally(() => {
        if (!cancelado) setCargando(false)
      })
    return () => {
      cancelado = true
    }
  }, [chatId, onSesionExpirada, t])

  return (
    <Modal labelledBy="detalle-chat-h" onCerrar={onCerrar}>
      <div className="rounded-2xl bg-white shadow-xl">
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 p-5">
          <div>
            <h2 id="detalle-chat-h" className="text-lg font-semibold text-slate-900">
              {t('panelChats.detalle.titulo')}
            </h2>
            <p className="mt-0.5 text-xs text-slate-600 font-mono break-all">{chatId}</p>
          </div>
          <button
            type="button"
            onClick={onCerrar}
            aria-label={t('panelChats.cerrarDetalle')}
            className="inline-flex items-center justify-center min-w-[44px] min-h-[44px] rounded-lg border border-slate-500 bg-white text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1"
          >
            <Ic.X size={18} />
          </button>
        </header>

        <div className="p-5">
          {cargando && <p className="text-sm text-slate-600">{t('panelChats.cargando')}</p>}
          {error && (
            <p role="alert" className="inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
              <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
              {error}
            </p>
          )}
          {detalle && detalle.interacciones.length === 0 && (
            <p className="text-sm text-slate-600">{t('panelChats.vacio')}</p>
          )}
          {detalle && detalle.interacciones.length > 0 && (
            <ol className="space-y-5 list-none m-0 p-0">
              {detalle.interacciones.map(interaccion => (
                <TurnoInteraccion key={interaccion.id} interaccion={interaccion} idioma={i18n.language} />
              ))}
            </ol>
          )}
        </div>
      </div>
    </Modal>
  )
}

function TurnoInteraccion({
  interaccion,
  idioma,
}: {
  interaccion: ChatInteraccion
  idioma: string
}) {
  const { t } = useTranslation()
  const fecha = new Date(interaccion.creado_en).toLocaleString(idioma, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <li className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs font-semibold text-slate-700">
          {t('panelChats.detalle.turno', { n: interaccion.turno })}
          <span className="text-slate-500 font-normal"> · <time dateTime={interaccion.creado_en}>{fecha}</time></span>
        </p>
        <VeredictoChip veredicto={interaccion.veredicto} />
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
          {t('panelChats.detalle.consulta')}
        </h3>
        <p className="mt-1 text-sm text-slate-900 whitespace-pre-wrap break-words">{interaccion.consulta}</p>
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
          {t('panelChats.detalle.respuesta')}
        </h3>
        <p className="mt-1 text-sm text-slate-900 whitespace-pre-wrap break-words">{interaccion.mensaje}</p>
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
          {t('panelChats.detalle.citas')}
        </h3>
        {interaccion.citas.length === 0 ? (
          <p className="mt-1 text-sm text-slate-500 italic">{t('panelChats.detalle.sinCitas')}</p>
        ) : (
          <ol className="mt-1 space-y-1 list-decimal list-inside">
            {interaccion.citas.map(cita => (
              <li key={`${interaccion.id}-cita-${cita.n}`} className="text-sm text-slate-800">
                <span className="font-medium">{cita.titulo}</span>
                {cita.slug && <span className="text-slate-500 font-mono"> · {cita.slug}</span>}
              </li>
            ))}
          </ol>
        )}
      </div>

      {interaccion.razon_escalamiento && (
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
            {t('panelChats.detalle.razonEscalamiento')}
          </h3>
          <p className="mt-1 text-sm text-slate-900">{interaccion.razon_escalamiento}</p>
        </div>
      )}

      <p className="text-xs text-slate-500 border-t border-slate-200 pt-2">
        {t('panelChats.detalle.metadatos', {
          proveedor: interaccion.proveedor,
          modelo: interaccion.modelo,
          latencia: interaccion.latencia_ms,
        })}
      </p>
    </li>
  )
}
