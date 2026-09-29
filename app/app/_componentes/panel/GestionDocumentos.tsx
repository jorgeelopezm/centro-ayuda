'use client'

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import type { Idioma } from '@/types'
import {
  eliminarDocumento,
  listarDocumentos,
  subirDocumento,
  type DocumentoAdmin,
  type EstadoDocumento,
} from '@/data/admin'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'

// Mimes admitidos (espeja `MIMES_ADMITIDOS` del backend en `api/app/troceo.py`).
// El atributo `accept` del input filtra el diálogo del sistema; el servidor
// vuelve a validar por magic bytes (autoridad final).
const ACEPTA =
  '.pdf,.docx,.md,.markdown,.txt,' +
  'application/pdf,' +
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document,' +
  'text/markdown,text/plain'

const INTERVALO_POLLING_MS = 3000

/**
 * Formatea bytes a un tamaño legible. Mantiene precisión mínima para no ruido
 * (0.1 MB para archivos > 1 MB; sin decimales para KB).
 */
function formatearTamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Gestión de documentos (solo Administrador). La ruta ya está protegida por el
 * Server Component; cada operación la vuelve a autorizar el backend por sesión
 * y nivel. El aislamiento por portal lo garantiza el backend (portal_id sale
 * del host de la petición, no del cliente).
 */
export function GestionDocumentos({ idioma }: { idioma: Idioma }) {
  const { t } = useTranslation()
  const router = useRouter()

  const [documentos, setDocumentos] = useState<DocumentoAdmin[]>([])
  const [aviso, setAviso] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [subiendo, setSubiendo] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  async function cargar() {
    const resp = await listarDocumentos()
    if (resp.ok) {
      setDocumentos((await resp.json()) as DocumentoAdmin[])
      setError(null)
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else {
      setError(t('gestionDocumentos.errorCargar'))
    }
  }

  useEffect(() => {
    void cargar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idioma])

  // Polling mientras haya documentos en ingesta. Se detiene solo cuando todos
  // están en `listo` o `error`, para no consumir red innecesariamente.
  useEffect(() => {
    const enProceso = documentos.some(
      d => d.estado === 'pendiente' || d.estado === 'procesando',
    )
    if (!enProceso) return
    const id = window.setInterval(() => {
      void cargar()
    }, INTERVALO_POLLING_MS)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentos])

  async function subir(archivo: File) {
    setSubiendo(true)
    setError(null)
    setAviso(null)
    try {
      const resp = await subirDocumento(archivo)
      if (resp.ok || resp.status === 201) {
        setAviso(t('gestionDocumentos.subido', { nombre: archivo.name }))
        await cargar()
      } else if (resp.status === 401) {
        router.replace(rutas.login(idioma))
      } else if (resp.status === 422) {
        setError(t('gestionDocumentos.errorFormato'))
      } else if (resp.status === 409) {
        setError(t('gestionDocumentos.errorSinProveedor'))
      } else {
        setError(t('gestionDocumentos.errorGuardar'))
      }
    } finally {
      setSubiendo(false)
    }
  }

  async function borrar(documento: DocumentoAdmin) {
    if (!window.confirm(t('gestionDocumentos.confirmarEliminar', { nombre: documento.nombre }))) {
      return
    }
    setError(null)
    const resp = await eliminarDocumento(documento.id)
    if (resp.ok || resp.status === 204) {
      setAviso(t('gestionDocumentos.eliminado', { nombre: documento.nombre }))
      await cargar()
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else if (resp.status === 404) {
      // Otro admin ya lo borró; refresca la lista.
      await cargar()
    } else {
      setError(t('gestionDocumentos.errorEliminar'))
    }
  }

  const columnas = ['nombre', 'idioma', 'estado', 'tamano', 'accion'] as const

  return (
    <main id="main-content" tabIndex={-1} className="focus:outline-none">
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          <Link
            href={rutas.panel(idioma)}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--acento)] hover:text-[var(--acento-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 rounded min-h-[44px]"
          >
            <Ic.ArrowLeft size={15} />
            {t('gestionDocumentos.volver')}
          </Link>
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--acento)] uppercase tracking-widest mt-2 mb-1">
            <Ic.FileText size={14} />
            {t('gestionDocumentos.seccion')}
          </div>
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'var(--font-serif), serif' }}>
            {t('gestionDocumentos.titulo')}
          </h1>
          <p className="text-slate-600 text-sm mt-1">{t('gestionDocumentos.subtitulo')}</p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <div role="status" aria-live="polite" className="min-h-[1.5rem]">
          {aviso && (
            <p className="inline-flex items-center gap-2 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-2 rounded-lg">
              <Ic.CheckCircle size={15} className="text-emerald-700 shrink-0" />
              {aviso}
            </p>
          )}
        </div>
        <div role="alert" aria-live="assertive" className="min-h-[1.25rem]">
          {error && (
            <p className="inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
              <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between gap-4 flex-wrap">
          <h2 className="text-xl font-semibold text-slate-900">{t('gestionDocumentos.lista')}</h2>
          <label
            className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold cursor-pointer hover:opacity-90 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-[var(--acento-foco)] min-h-[44px]"
            style={{ background: 'var(--acento)' }}
          >
            <Ic.Upload size={15} />
            {subiendo ? t('gestionDocumentos.subiendo') : t('gestionDocumentos.subir')}
            <input
              ref={inputRef}
              type="file"
              accept={ACEPTA}
              disabled={subiendo}
              onChange={e => {
                const archivo = e.target.files?.[0]
                if (archivo) void subir(archivo)
                e.target.value = '' // permite volver a elegir el mismo archivo
              }}
              aria-label={t('gestionDocumentos.subir')}
              className="sr-only"
            />
          </label>
        </div>

        <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label={t('gestionDocumentos.tablaAria')}>
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  {columnas.map(columna => (
                    <th
                      key={columna}
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-bold text-slate-600 uppercase tracking-wider whitespace-nowrap"
                    >
                      {t(`gestionDocumentos.columnas.${columna}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {documentos.map(documento => (
                  <tr key={documento.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3.5 text-slate-800 font-medium break-all">
                      {documento.nombre}
                      {/* Motivo del error visible bajo el nombre cuando el
                          estado es `error`: ver el detalle sin depender del
                          tooltip del chip (mejor UX y accesibilidad). */}
                      {documento.estado === 'error' && documento.errorDetalle && (
                        <p className="mt-1 text-xs font-normal text-red-700 break-words">
                          {documento.errorDetalle}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3.5 text-slate-700">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-slate-300 text-slate-700 bg-slate-50">
                        {t(`gestionDocumentos.idiomas.${documento.idioma}`)}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <EstadoPill estado={documento.estado} detalle={documento.errorDetalle} />
                    </td>
                    <td className="px-4 py-3.5 text-slate-600 whitespace-nowrap tabular-nums">
                      {formatearTamano(documento.bytes)}
                    </td>
                    <td className="px-4 py-3.5">
                      <button
                        type="button"
                        onClick={() => void borrar(documento)}
                        aria-label={t('gestionDocumentos.eliminarAria', { nombre: documento.nombre })}
                        className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-red-200 text-red-800 bg-red-50 hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                      >
                        <Ic.Trash size={14} />
                        {t('gestionDocumentos.eliminar')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {documentos.length === 0 && (
            <p className="px-4 py-6 text-sm text-slate-600">{t('gestionDocumentos.vacio')}</p>
          )}
        </div>
      </div>
    </main>
  )
}

/**
 * Chip de estado con icono y color por estado. El icono duplica la información
 * del color (WCAG 1.4.1: la información no puede depender solo del color).
 */
function EstadoPill({ estado, detalle }: { estado: EstadoDocumento; detalle: string | null }) {
  const { t } = useTranslation()
  const texto = t(`gestionDocumentos.estados.${estado}`)
  if (estado === 'listo') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-emerald-200 text-emerald-800 bg-emerald-50">
        <Ic.CheckCircle size={12} className="text-emerald-700" />
        {texto}
      </span>
    )
  }
  if (estado === 'error') {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-red-200 text-red-800 bg-red-50"
        title={detalle ?? undefined}
      >
        <Ic.AlertCircle size={12} className="text-red-700" />
        {texto}
      </span>
    )
  }
  // pendiente | procesando: mismo aspecto neutro con reloj.
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border border-slate-300 text-slate-700 bg-slate-100">
      <Ic.Clock size={12} className="text-slate-600" />
      {texto}
    </span>
  )
}
