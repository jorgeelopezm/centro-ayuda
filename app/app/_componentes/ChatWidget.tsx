'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import type { Idioma } from '@/types'
import { consultarChat, ErrorChat, serializarConversacion, type FuenteChat, type RespuestaChat, type TurnoChat } from '@/data/chat'
import { traducir } from '@/i18n/traducir'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'

const SELECTOR_FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Mensajes que renderiza el widget. Se derivan de los turnos que se envían al
 * backend (`TurnoChat[]`) más el veredicto y las fuentes de cada respuesta
 * del asistente. Al pintar, cada `[n]` del `mensaje` se convierte en enlace a
 * la fuente correspondiente.
 */
type MensajeUsuario = { autor: 'usuario'; texto: string }
type MensajeAsistente = {
  autor: 'asistente'
  veredicto: RespuestaChat['veredicto']
  mensaje: string
  fuentes: FuenteChat[]
  razon: RespuestaChat['razon']
  /** Conversación serializada por el backend cuando `veredicto === 'escalar'`. */
  conversacion: TurnoChat[]
}
type MensajeUI = MensajeUsuario | MensajeAsistente

/** Divide un texto con marcas `[1]`, `[2]`… en trozos alternados de texto y cita. */
type Trozo = { tipo: 'texto'; texto: string } | { tipo: 'cita'; n: number }

function trocearConCitas(texto: string): Trozo[] {
  const trozos: Trozo[] = []
  const patron = /\[(\d+)\]/g
  let ultimoFin = 0
  let coincidencia: RegExpExecArray | null
  while ((coincidencia = patron.exec(texto)) !== null) {
    if (coincidencia.index > ultimoFin) {
      trozos.push({ tipo: 'texto', texto: texto.slice(ultimoFin, coincidencia.index) })
    }
    trozos.push({ tipo: 'cita', n: Number(coincidencia[1]) })
    ultimoFin = coincidencia.index + coincidencia[0].length
  }
  if (ultimoFin < texto.length) trozos.push({ tipo: 'texto', texto: texto.slice(ultimoFin) })
  return trozos
}

function MensajeAsistenteVista({
  mensaje,
  idioma,
  onSoporte,
}: {
  mensaje: MensajeAsistente
  idioma: Idioma
  onSoporte: () => void
}) {
  const t = traducir(idioma)
  const avatar = (
    <div className="shrink-0 w-7 h-7 rounded-full bg-[var(--acento-claro)] flex items-center justify-center mt-0.5">
      <Ic.Sparkles size={13} className="text-[var(--acento)]" />
    </div>
  )

  const trozos = trocearConCitas(mensaje.mensaje)
  const fuentesPorN = new Map(mensaje.fuentes.map(f => [f.n, f]))

  const necesitaEscalar = mensaje.veredicto === 'escalar' || mensaje.veredicto === 'sin_resultados'
  const conAviso = mensaje.veredicto !== 'respondida'

  const claseBurbuja = conAviso
    ? 'bg-amber-50 border border-amber-200 rounded-2xl rounded-tl-none px-3.5 py-2.5'
    : 'bg-slate-50 rounded-2xl rounded-tl-none px-3.5 py-2.5'

  return (
    <div className="flex items-start gap-2.5">
      {avatar}
      <div className="space-y-2 max-w-[85%]">
        <div className={claseBurbuja}>
          {conAviso && (
            <div className="flex items-center gap-1.5 mb-1.5">
              <Ic.Warning size={13} className="text-amber-700 shrink-0" />
              <p className="text-amber-800 text-[11px] font-semibold">{t(`chat.${etiquetaAviso(mensaje)}`)}</p>
            </div>
          )}
          <p className="text-slate-700 text-sm leading-relaxed">
            {trozos.map((tr, i) => {
              if (tr.tipo === 'texto') return <span key={i}>{tr.texto}</span>
              const fuente = fuentesPorN.get(tr.n)
              if (!fuente) return <sup key={i} className="text-slate-400">[{tr.n}]</sup>
              if (fuente.tipo === 'articulo' && fuente.slug) {
                return (
                  <sup key={i}>
                    <Link
                      href={rutas.articulo(idioma, fuente.slug)}
                      aria-label={t('chat.fuenteAria', { n: fuente.n })}
                      className="text-[var(--acento)] hover:text-[var(--acento-hover)] font-bold ml-0.5 text-[11px] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--acento-foco)] rounded"
                    >
                      [{fuente.n}]
                    </Link>
                  </sup>
                )
              }
              // Documento: no navegable (no hay ruta pública); marcado como cita textual.
              return (
                <sup
                  key={i}
                  aria-label={t('chat.documentoAria', { titulo: fuente.titulo })}
                  className="text-[var(--acento)] font-bold ml-0.5 text-[11px]"
                >
                  [{fuente.n}]
                </sup>
              )
            })}
          </p>
        </div>

        {mensaje.fuentes.length > 0 && <BloqueFuentes fuentes={mensaje.fuentes} idioma={idioma} />}

        {necesitaEscalar && (
          <button
            type="button"
            onClick={onSoporte}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px]"
          >
            <Ic.Mail size={15} />
            {t('chat.contactarSoporte')}
          </button>
        )}
      </div>
    </div>
  )
}

/** Traduce el veredicto/razon a la clave i18n del aviso (leyenda amarilla). */
function etiquetaAviso(m: MensajeAsistente): string {
  if (m.veredicto === 'sin_resultados') return 'sinResultados'
  if (m.veredicto === 'fuera_de_scope') return 'fueraDeScope'
  if (m.veredicto === 'escalar') {
    if (m.razon === 'solicitud_usuaria') return 'escalarUsuaria'
    if (m.razon === 'error_proveedor') return 'escalarError'
    return 'escalarTope'
  }
  return 'bienvenida'
}

function BloqueFuentes({ fuentes, idioma }: { fuentes: FuenteChat[]; idioma: Idioma }) {
  const t = traducir(idioma)
  return (
    <div className="bg-white border border-slate-200 rounded-xl px-3 py-2.5 space-y-1.5">
      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{t('chat.fuentes')}</p>
      {fuentes.map(f => {
        if (f.tipo === 'articulo' && f.slug) {
          return (
            <Link
              key={f.n}
              href={rutas.articulo(idioma, f.slug)}
              className="flex items-start gap-1.5 text-[12px] text-[var(--acento)] hover:text-[var(--acento-hover)] hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--acento-foco)] rounded leading-snug"
            >
              <Ic.ExternalLink size={11} className="shrink-0 mt-0.5" />
              <span>
                <strong>[{f.n}]</strong> {f.titulo}
              </span>
            </Link>
          )
        }
        // Documentos: sin enlace navegable (viven en `admin/documentos`, no en la web pública).
        return (
          <div key={f.n} className="flex items-start gap-1.5 text-[12px] text-slate-700 leading-snug">
            <Ic.FileText size={11} className="shrink-0 mt-0.5 text-slate-500" />
            <span>
              <strong>[{f.n}]</strong> {f.titulo}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function MensajeUsuarioVista({ mensaje }: { mensaje: MensajeUsuario }) {
  return (
    <div className="flex justify-end">
      <div className="rounded-2xl rounded-tr-none px-3.5 py-2.5 max-w-[85%] text-white text-sm" style={{ background: 'var(--acento)' }}>
        {mensaje.texto}
      </div>
    </div>
  )
}

/**
 * Widget conectado al BFF del chat. Mantiene el estado local (mensajes,
 * chatId, cargando) y llama a `consultarChat` con el historial acumulado.
 * El `chat_id` que devuelve el backend en la primera respuesta se reutiliza
 * en las siguientes; si expira o cambia, se adopta el nuevo.
 *
 * Escalamiento: al pulsar "Contactar soporte", se pide al backend una
 * confirmación con `solicitar_soporte: true` (obtiene la `conversacion`
 * serializada) y luego se abre un `mailto:` con esa conversación en el body.
 * Cuando `configurar-correo-soporte` esté listo, este `mailto:` se sustituye
 * por el formulario, sin tocar el resto del widget.
 */
export function ChatWidget({ idioma, onClose }: { idioma: Idioma; onClose: () => void }) {
  const t = traducir(idioma)
  const dialogoRef = useRef<HTMLDivElement>(null)
  const cerrarRef = useRef<HTMLButtonElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const entradaRef = useRef<HTMLInputElement>(null)

  // Mensajes: arranca con el saludo (no se envía al backend, solo se pinta).
  const [mensajes, setMensajes] = useState<MensajeUI[]>([
    { autor: 'asistente', veredicto: 'respondida', mensaje: t('chat.bienvenida'), fuentes: [], razon: null, conversacion: [] },
  ])
  const [entrada, setEntrada] = useState('')
  const [cargando, setCargando] = useState(false)
  const [chatId, setChatId] = useState<string | null>(null)
  const [errorTextoClave, setErrorTextoClave] = useState<string | null>(null)

  // Retención de foco y cierre con Escape (herencia del widget anterior).
  useEffect(() => {
    cerrarRef.current?.focus()

    const alPulsar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab') return

      const dialogo = dialogoRef.current
      if (!dialogo) return
      const focusables = Array.from(dialogo.querySelectorAll<HTMLElement>(SELECTOR_FOCUSABLE)).filter(
        el => !el.hasAttribute('disabled'),
      )
      if (focusables.length === 0) return

      const primero = focusables[0]
      const ultimo = focusables[focusables.length - 1]
      const activo = document.activeElement

      if (e.shiftKey && (activo === primero || !dialogo.contains(activo))) {
        e.preventDefault()
        ultimo.focus()
      } else if (!e.shiftKey && activo === ultimo) {
        e.preventDefault()
        primero.focus()
      }
    }

    document.addEventListener('keydown', alPulsar)
    return () => document.removeEventListener('keydown', alPulsar)
  }, [onClose])

  // Auto-scroll al fondo cuando llegan mensajes nuevos.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [mensajes, cargando])

  /** Construye el historial de turnos (solo `usuario`) a enviar al backend.
   *
   * El backend rechaza turnos con `rol: 'asistente'` (schema `TurnoChatIn`)
   * para prevenir inyección por "asistente falso"; el LLM tiende a tratar los
   * turnos de assistant como contexto autoritativo. La conversación completa
   * con turnos de asistente sigue viajando de vuelta al cliente en
   * `RespuestaChat.conversacion` para el mailto de escalamiento (serializada
   * en el servidor). Persistir historial server-side por `session_id` queda
   * para el cambio posterior `historial-chat-server`. */
  const historialDeMensajes = (ms: MensajeUI[]): TurnoChat[] =>
    ms
      .filter((m): m is MensajeUsuario => m.autor === 'usuario')
      .map<TurnoChat>(m => ({ rol: 'usuario', texto: m.texto }))
      .filter(t => t.texto.trim().length > 0)

  const enviarConsulta = useCallback(
    async (texto: string) => {
      if (!texto.trim() || cargando) return
      setErrorTextoClave(null)
      const nuevoUsuario: MensajeUsuario = { autor: 'usuario', texto: texto.trim() }
      // Snapshot del historial ANTES de agregar la consulta actual (el backend
      // recibe el historial previo + la consulta en el campo `consulta`).
      const historial = historialDeMensajes(mensajes)
      setMensajes(m => [...m, nuevoUsuario])
      setEntrada('')
      setCargando(true)
      try {
        const resp = await consultarChat(idioma, {
          consulta: texto.trim(),
          historial,
          chatId,
        })
        setChatId(resp.chat_id)
        setMensajes(m => [
          ...m,
          {
            autor: 'asistente',
            veredicto: resp.veredicto,
            mensaje: resp.mensaje,
            fuentes: resp.fuentes,
            razon: resp.razon,
            conversacion: resp.conversacion,
          },
        ])
      } catch (err) {
        if (err instanceof ErrorChat) {
          if (err.estado === 429) setErrorTextoClave('chat.errorTasa')
          else if (err.estado === 503) setErrorTextoClave('chat.mantenimiento')
          else setErrorTextoClave('chat.errorRed')
        } else {
          setErrorTextoClave('chat.errorRed')
        }
      } finally {
        setCargando(false)
        // Devolver el foco al input tras completar (no interrumpe si el usuario ya movió el foco).
        requestAnimationFrame(() => {
          if (document.activeElement === document.body) entradaRef.current?.focus()
        })
      }
    },
    [cargando, mensajes, idioma, chatId],
  )

  const abrirSoporte = useCallback(async () => {
    // Se pide al backend la conversación completa (canonicaliza el historial
    // que el cliente venía manteniendo). Si falla, se serializa lo local.
    let conversacionTexto: string
    try {
      const resp = await consultarChat(idioma, {
        consulta: t('chat.contactarSoporte'),
        historial: historialDeMensajes(mensajes),
        chatId,
        solicitarSoporte: true,
      })
      conversacionTexto = serializarConversacion(resp.conversacion, idioma)
    } catch {
      conversacionTexto = serializarConversacion(historialDeMensajes(mensajes), idioma)
    }
    // `mailto:` legacy hasta que se cablee al formulario del cambio
    // `configurar-correo-soporte`. Se codifica el body con `encodeURIComponent`
    // para no romper con saltos de línea ni caracteres reservados.
    const asunto = encodeURIComponent(t('chat.titulo'))
    const cuerpo = encodeURIComponent(conversacionTexto)
    window.location.href = `mailto:soporte@empresa.example?subject=${asunto}&body=${cuerpo}`
  }, [idioma, mensajes, chatId, t])

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    void enviarConsulta(entrada)
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm" aria-hidden="true" onClick={onClose} />

      <div
        ref={dialogoRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="chat-titulo"
        className="fixed bottom-6 right-6 z-50 w-[360px] max-w-[calc(100vw-3rem)] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden border border-slate-200"
        style={{ maxHeight: 'min(600px, calc(100vh - 3rem))' }}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100" style={{ background: 'var(--acento)' }}>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
              <Ic.Sparkles size={15} className="text-white" />
            </div>
            <div>
              <h2 id="chat-titulo" className="text-white font-semibold text-sm leading-none">
                {t('chat.titulo')}
              </h2>
              <p className="text-indigo-100 text-[11px] mt-0.5">{t('chat.subtitulo')}</p>
            </div>
          </div>
          <button
            ref={cerrarRef}
            type="button"
            onClick={onClose}
            aria-label={t('chat.cerrar')}
            className="w-11 h-11 rounded-lg flex items-center justify-center text-white hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white transition-colors"
          >
            <Ic.X size={18} />
          </button>
        </div>

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0"
          aria-live="polite"
          aria-atomic="false"
          aria-busy={cargando}
          aria-label={t('chat.conversacionAria')}
        >
          {mensajes.map((m, i) =>
            m.autor === 'usuario' ? (
              <MensajeUsuarioVista key={i} mensaje={m} />
            ) : (
              <MensajeAsistenteVista key={i} mensaje={m} idioma={idioma} onSoporte={abrirSoporte} />
            ),
          )}
          {cargando && (
            <p className="text-[12px] text-slate-500 italic pl-9" role="status">
              {t('chat.cargando')}
            </p>
          )}
          {errorTextoClave && (
            <p className="text-[12px] text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2" role="alert">
              {t(errorTextoClave)}
            </p>
          )}
        </div>

        <form onSubmit={onSubmit} className="border-t border-slate-100 px-4 py-3 bg-white">
          <label htmlFor="chat-entrada" className="block text-[11px] font-medium text-slate-600 mb-1.5">
            {t('chat.entradaEtiqueta')}
          </label>
          <div className="flex items-center gap-2">
            <input
              ref={entradaRef}
              id="chat-entrada"
              type="text"
              value={entrada}
              onChange={e => setEntrada(e.target.value)}
              placeholder={t('chat.entradaMarcador')}
              aria-describedby="chat-nota"
              disabled={cargando}
              maxLength={500}
              className="flex-1 px-3 py-2 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:border-transparent disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={cargando || entrada.trim().length === 0}
              aria-label={t('chat.enviar')}
              className="w-11 h-11 shrink-0 rounded-lg flex items-center justify-center text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-opacity hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: 'var(--acento)' }}
            >
              <Ic.Send size={16} />
            </button>
          </div>
          <p id="chat-nota" className="text-[10px] text-slate-500 mt-1.5 leading-snug">
            {t('chat.nota')}
          </p>
        </form>
      </div>
    </>
  )
}
