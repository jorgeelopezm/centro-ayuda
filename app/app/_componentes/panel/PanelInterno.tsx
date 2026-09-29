'use client'

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import type { ContenidoIdioma, Idioma, PlantillaCentroAyuda } from '@/types'
import {
  comprobarSaludIA,
  eliminarArticulo,
  eliminarCategoria,
  guardarConfigIA,
  guardarEmpresa,
  guardarMarca,
  guardarPlantilla,
  guardarGithub,
  listarCategorias,
  listarPreguntas,
  obtenerArticulo,
  obtenerConfigIA,
  subirLogo,
  type ArticuloAdmin,
  type CategoriaAdmin,
  type ConfigIAAdmin,
  type ConfigIAPayload,
  type EstadoSaludIA,
  type PreguntaAdmin,
  type RolIA,
  type SaludRolIA,
} from '@/data/admin'
import { derivarDegradadoBanner, derivarTokensAcento, validarPaleta } from '@/seguridad/contraste'
import { esAdministrador, esSuperAdmin } from '@/auth/nivel'
import { fechaLegible } from '@/i18n/fechas'
import { rutas } from '@/i18n/rutas'
import { Ic } from '@/components/iconos'
import { KcsChip } from '@/components/KcsChip'
import { ArticuloForm } from '@/components/ArticuloForm'
import { CategoriaForm } from '@/components/CategoriaForm'
import { Modal } from '@/components/Modal'
import { Tabs, type Pestana } from '@/components/Tabs'
import { resolverPestana, type PestanaId } from '@/panel/panelPestanas'
import { PLANTILLAS, resolverPlantilla } from '@/plantillas/plantillas'
import { PanelChats } from './PanelChats'
import { PanelSugerencias } from './PanelSugerencias'

const ICONO_METRICA = {
  sinResolver: { icono: <Ic.HelpCircle size={22} className="text-[var(--acento)]" />, fondo: 'bg-[var(--acento-claro)]' },
  conCita: { icono: <Ic.CheckCircle size={22} className="text-emerald-700" />, fondo: 'bg-emerald-50' },
  creados: { icono: <Ic.FileText size={22} className="text-purple-700" />, fondo: 'bg-purple-50' },
} as const

const FILTROS = ['todas', 'nueva', 'revision', 'cubierta'] as const

/**
 * Presentación de cada estado del sondeo de salud.
 *
 * WCAG 2.2 AA (criterio 1.4.1): el estado **no** se comunica solo con color. Cada
 * uno lleva su propio icono y una etiqueta de texto traducida; el color es
 * refuerzo, nunca el único portador de la información. Los tonos van sobre blanco
 * con contraste ≥ 4.5:1 (`-700` de la paleta Tailwind).
 */
const SALUD_PRESENTACION: Record<
  EstadoSaludIA,
  { Icono: typeof Ic.CheckCircle; clase: string }
> = {
  ok: { Icono: Ic.CheckCircle, clase: 'text-emerald-700' },
  sin_clave: { Icono: Ic.AlertCircle, clase: 'text-slate-700' },
  credenciales: { Icono: Ic.Lock, clase: 'text-rose-700' },
  saldo: { Icono: Ic.CreditCard, clase: 'text-rose-700' },
  timeout: { Icono: Ic.Clock, clase: 'text-amber-700' },
  error: { Icono: Ic.Warning, clase: 'text-rose-700' },
}

type FormState = { modo: 'crear' | 'editar'; inicial?: ArticuloAdmin; preguntaId?: number }

/**
 * Panel interno. Portado desde la SPA: mismo marcado y ARIA (pestañas, tabla,
 * avisos). El nivel y el contenido llegan del Server Component (guardia previa);
 * las preguntas y la config de IA se piden al BFF en cliente. `router.refresh()`
 * sustituye al revalidator para releer el contenido del servidor tras un cambio.
 */
export function PanelInterno({
  idioma,
  nivel,
  contenido,
}: {
  idioma: Idioma
  nivel: number
  contenido: ContenidoIdioma
}) {
  const { t, i18n } = useTranslation()
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const [filtro, setFiltro] = useState<(typeof FILTROS)[number]>('todas')
  const [preguntas, setPreguntas] = useState<PreguntaAdmin[]>([])
  const [formulario, setFormulario] = useState<FormState | null>(null)
  const [aviso, setAviso] = useState<{ texto: string; tono: 'exito' | 'error' } | null>(null)
  const avisoExito = (texto: string) => setAviso({ texto, tono: 'exito' })
  const avisoError = (texto: string) => setAviso({ texto, tono: 'error' })
  const [empresaInput, setEmpresaInput] = useState(contenido.empresa)
  const [configIA, setConfigIA] = useState<ConfigIAAdmin | null>(null)
  // Estado por rol: proveedor seleccionado en el selector, clave tecleada,
  // y si el usuario ha pulsado «Editar» para reescribir una clave existente.
  const [proveedorInput, setProveedorInput] = useState<Record<RolIA, string>>({
    chat: '', traduccion: '', embeddings: '',
  })
  const [claveInput, setClaveInput] = useState<Record<RolIA, string>>({
    chat: '', traduccion: '', embeddings: '',
  })
  const [editandoClave, setEditandoClave] = useState<Record<RolIA, boolean>>({
    chat: false, traduccion: false, embeddings: false,
  })
  const [confirmarBorrado, setConfirmarBorrado] = useState<{ rol: RolIA; proveedor: string } | null>(null)
  // Salud de los proveedores. Nace vacía a propósito: sondearla hace llamadas
  // salientes reales, así que solo ocurre cuando SuperAdmin pulsa «Comprobar».
  const [saludIA, setSaludIA] = useState<Record<RolIA, SaludRolIA> | null>(null)
  const [comprobandoSalud, setComprobandoSalud] = useState(false)
  const [categorias, setCategorias] = useState<CategoriaAdmin[]>([])
  const [formCategoria, setFormCategoria] = useState<{ modo: 'crear' | 'editar'; inicial?: CategoriaAdmin } | null>(null)
  const [acento, setAcento] = useState(contenido.acento)
  const [subiendoLogo, setSubiendoLogo] = useState(false)
  // Plantilla del sitio público: `plantillaInput` es lo que el Administrador está
  // eligiendo y `plantillaGuardada` la última confirmada por el servidor, a la que se
  // vuelve si el guardado falla (la activa no cambia sin confirmación).
  const [plantillaInput, setPlantillaInput] = useState<PlantillaCentroAyuda>(resolverPlantilla(contenido.plantilla))
  const [plantillaGuardada, setPlantillaGuardada] = useState<PlantillaCentroAyuda>(resolverPlantilla(contenido.plantilla))
  const [guardandoPlantilla, setGuardandoPlantilla] = useState(false)
  // Enlace de GitHub del portal (icono de la cabecera de documentación). Vacío = sin enlace.
  const [githubInput, setGithubInput] = useState(contenido.githubUrl ?? '')
  const [guardandoGithub, setGuardandoGithub] = useState(false)
  const [errorGithub, setErrorGithub] = useState<string | null>(null)

  const puedeAdministrar = esAdministrador(nivel)
  // La config de IA es global de la plataforma (una sola clave/proveedor para todos los
  // portales): solo la gestiona el SuperAdmin. El Administrador de un portal sí ve la
  // pestaña «Administración» (empresa, marca y logo son suyos), pero no este formulario;
  // así tampoco dispara un fetch que el backend responde 403.
  const puedeConfigurarIA = esSuperAdmin(nivel)

  // Helpers para leer el estado del proveedor seleccionado en cada rol.
  function estadoDe(rol: RolIA) {
    const seleccionado = proveedorInput[rol]
    const p = configIA?.proveedores.find(x => x.id === seleccionado) ?? null
    const configurada = !!p?.configurada
    return {
      seleccionado,
      proveedores: configIA?.rolesSoportados[rol] ?? [],
      configurada,
      pista: p?.pista ?? null,
      editando: editandoClave[rol] || !configurada,
    }
  }

  function seleccionarProveedor(rol: RolIA, id: string) {
    setProveedorInput(prev => ({ ...prev, [rol]: id }))
    // Al cambiar de proveedor, volver a solo lectura y descartar lo tecleado: cada
    // proveedor tiene su propia clave y no debe arrastrarse entre ellos.
    setEditandoClave(prev => ({ ...prev, [rol]: false }))
    setClaveInput(prev => ({ ...prev, [rol]: '' }))
  }

  async function cargarPreguntas() {
    const resp = await listarPreguntas(idioma)
    if (resp.ok) setPreguntas((await resp.json()) as PreguntaAdmin[])
    else if (resp.status === 401) router.replace(rutas.login(idioma))
  }

  async function cargarCategorias() {
    const resp = await listarCategorias()
    if (resp.ok) setCategorias((await resp.json()) as CategoriaAdmin[])
    else if (resp.status === 401) router.replace(rutas.login(idioma))
  }

  async function cargarConfigIA() {
    const resp = await obtenerConfigIA()
    if (resp.ok) {
      const cfg = (await resp.json()) as ConfigIAAdmin
      setConfigIA(cfg)
      // El selector arranca en el valor guardado del rol, o en el primero de la
      // lista de proveedores admitidos por ese rol si aún no hay elección.
      setProveedorInput({
        chat: cfg.proveedorChat ?? cfg.rolesSoportados.chat[0] ?? '',
        traduccion: cfg.proveedorTraduccion ?? cfg.rolesSoportados.traduccion[0] ?? '',
        embeddings: cfg.proveedorEmbeddings ?? cfg.rolesSoportados.embeddings[0] ?? '',
      })
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    }
  }

  /**
   * Sondea los tres roles contra sus proveedores. Es la respuesta a «¿el 502 del
   * panel es culpa del proveedor o nuestra?»: distingue clave revocada, cuenta sin
   * saldo, timeout y caída, que hasta ahora solo se separaban leyendo los logs.
   */
  async function comprobarSaludHandler() {
    setComprobandoSalud(true)
    try {
      const resp = await comprobarSaludIA()
      if (resp.ok) {
        const { roles } = (await resp.json()) as { roles: SaludRolIA[] }
        setSaludIA(
          Object.fromEntries(roles.map(r => [r.rol, r])) as Record<RolIA, SaludRolIA>,
        )
      } else if (resp.status === 401) {
        router.replace(rutas.login(idioma))
      } else {
        avisoError(t('configIA.salud.error'))
      }
    } catch {
      avisoError(t('configIA.salud.error'))
    } finally {
      setComprobandoSalud(false)
    }
  }

  useEffect(() => {
    void cargarPreguntas()
    void cargarCategorias()
    if (puedeConfigurarIA) void cargarConfigIA()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idioma])

  // El input del campo [Empresa] sigue al valor servido si cambia (tras refrescar).
  useEffect(() => {
    setEmpresaInput(contenido.empresa)
  }, [contenido.empresa])

  // El selector de acento sigue a la paleta servida tras guardar (router.refresh). El
  // banner ya no se edita: se deriva del acento al previsualizar y al guardar.
  useEffect(() => {
    setAcento(contenido.acento)
  }, [contenido.acento])

  const pestanaActiva = resolverPestana(searchParams.get('seccion'), puedeAdministrar)
  function cambiarPestana(id: PestanaId) {
    const proximo = new URLSearchParams(Array.from(searchParams.entries()))
    proximo.set('seccion', id)
    router.replace(`${pathname}?${proximo.toString()}`) // no ensucia el historial
  }

  async function guardarEmpresaHandler(evento: FormEvent) {
    evento.preventDefault()
    const nombre = empresaInput.trim()
    const resp = await guardarEmpresa(nombre)
    if (resp.ok) {
      avisoExito(t('ajustesEmpresa.guardado', { empresa: nombre }))
      router.refresh() // refresca el título y la marca con el nuevo valor
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else {
      avisoError(t('ajustesEmpresa.error', { empresa: nombre }))
    }
  }

  const CAMPO_PROVEEDOR_POR_ROL: Record<RolIA, keyof ConfigIAPayload> = {
    chat: 'proveedorChat',
    traduccion: 'proveedorTraduccion',
    embeddings: 'proveedorEmbeddings',
  }

  async function guardarRolHandler(rol: RolIA, evento: FormEvent) {
    evento.preventDefault()
    const proveedor = proveedorInput[rol]
    const clave = claveInput[rol].trim()
    const payload: ConfigIAPayload = {
      [CAMPO_PROVEEDOR_POR_ROL[rol]]: proveedor,
      ...(clave ? { proveedor, clave } : {}),
    }
    const resp = await guardarConfigIA(payload)
    if (resp.ok) {
      setConfigIA((await resp.json()) as ConfigIAAdmin)
      setClaveInput(prev => ({ ...prev, [rol]: '' }))
      setEditandoClave(prev => ({ ...prev, [rol]: false }))
      avisoExito(t('configIA.guardado'))
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else if (resp.status === 409) {
      avisoError(t('configIA.errorCifrado'))
    } else if (resp.status === 422) {
      avisoError(t('configIA.errorRolInvalido'))
    } else {
      avisoError(t('configIA.error'))
    }
  }

  async function confirmarBorradoClaveHandler() {
    if (!confirmarBorrado) return
    const { rol, proveedor } = confirmarBorrado
    const resp = await guardarConfigIA({ proveedor, borrarClave: true })
    setConfirmarBorrado(null)
    if (resp.ok) {
      setConfigIA((await resp.json()) as ConfigIAAdmin)
      setClaveInput(prev => ({ ...prev, [rol]: '' }))
      setEditandoClave(prev => ({ ...prev, [rol]: false }))
      avisoExito(t('configIA.eliminada', { proveedor }))
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else if (resp.status === 409) {
      // El backend devuelve `detail` con el nombre del rol en uso.
      const cuerpo = (await resp.json().catch(() => null)) as { detail?: string } | null
      avisoError(cuerpo?.detail ?? t('configIA.errorEnUso'))
    } else {
      avisoError(t('configIA.error'))
    }
  }

  async function guardarMarcaHandler(evento: FormEvent) {
    evento.preventDefault()
    const resp = await guardarMarca({ acento })
    if (resp.ok) {
      avisoExito(t('ajustesMarca.guardado'))
      router.refresh() // los tokens de la paleta se reinyectan en el layout servido
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else if (resp.status === 422) {
      // El servidor rechaza una paleta que no cumple contraste: nombra el par que falla.
      const cuerpo = (await resp.json().catch(() => null)) as
        | { detail?: { par?: string; ratio?: number; minimo?: number } }
        | null
      const d = cuerpo?.detail
      avisoError(
        d?.par
          ? t('ajustesMarca.errorContrastePar', { par: d.par, ratio: d.ratio, minimo: d.minimo })
          : t('ajustesMarca.errorContraste'),
      )
    } else {
      avisoError(t('ajustesMarca.error'))
    }
  }

  async function subirLogoHandler(archivo: File) {
    setSubiendoLogo(true)
    try {
      const resp = await subirLogo(archivo)
      if (resp.ok) {
        avisoExito(t('ajustesMarca.logoGuardado'))
        router.refresh() // la cabecera y el favicon pasan a mostrar el logo nuevo
      } else if (resp.status === 401) {
        router.replace(rutas.login(idioma))
      } else if (resp.status === 422) {
        avisoError(t('ajustesMarca.logoError'))
      } else {
        avisoError(t('ajustesMarca.error'))
      }
    } finally {
      setSubiendoLogo(false)
    }
  }

  async function guardarPlantillaHandler(evento: FormEvent) {
    evento.preventDefault()
    setGuardandoPlantilla(true)
    try {
      const resp = await guardarPlantilla(plantillaInput)
      if (resp.ok) {
        // La confirmación es la del servidor (el valor guardado), no lo que se creyó enviar.
        const cuerpo = (await resp.json().catch(() => null)) as { plantilla?: string } | null
        const confirmada = cuerpo?.plantilla ? resolverPlantilla(cuerpo.plantilla) : plantillaInput
        setPlantillaGuardada(confirmada)
        setPlantillaInput(confirmada)
        avisoExito(t('ajustesPlantilla.guardado'))
        router.refresh() // el sitio público pasa a servirse con el armazón nuevo
      } else if (resp.status === 401) {
        router.replace(rutas.login(idioma))
      } else {
        // Se conserva la plantilla anterior: la elección sin confirmar no queda marcada.
        setPlantillaInput(plantillaGuardada)
        avisoError(t('ajustesPlantilla.error'))
      }
    } catch {
      setPlantillaInput(plantillaGuardada)
      avisoError(t('ajustesPlantilla.error'))
    } finally {
      setGuardandoPlantilla(false)
    }
  }

  async function guardarGithubHandler(evento: FormEvent) {
    evento.preventDefault()
    setErrorGithub(null)
    setGuardandoGithub(true)
    try {
      const resp = await guardarGithub(githubInput.trim())
      if (resp.ok) {
        const cuerpo = (await resp.json().catch(() => null)) as { url?: string | null } | null
        const confirmada = cuerpo?.url ?? ''
        setGithubInput(confirmada)
        avisoExito(t(confirmada ? 'ajustesGithub.guardado' : 'ajustesGithub.borrado'))
        router.refresh() // la cabecera pública muestra u oculta el icono
      } else if (resp.status === 401) {
        router.replace(rutas.login(idioma))
      } else if (resp.status === 422) {
        // Error junto al campo (asociado con `aria-describedby`), no solo en el aviso.
        setErrorGithub(t('ajustesGithub.errorFormato'))
      } else {
        avisoError(t('ajustesGithub.error'))
      }
    } catch {
      avisoError(t('ajustesGithub.error'))
    } finally {
      setGuardandoGithub(false)
    }
  }

  async function recargarTodo() {
    await cargarPreguntas()
    router.refresh() // refresca el contenido (métricas, artículos) desde la API
  }

  async function cerrarSesion() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' })
    router.replace(rutas.login(idioma))
    router.refresh()
  }

  async function abrirEditar(id: string) {
    const resp = await obtenerArticulo(id)
    if (resp.ok) {
      setFormulario({ modo: 'editar', inicial: (await resp.json()) as ArticuloAdmin })
      setAviso(null)
    } else {
      avisoError(t('panelGestion.errorCargar'))
    }
  }

  async function eliminar(id: string, titulo: string) {
    if (!window.confirm(t('panelGestion.confirmarEliminar', { titulo }))) return
    const resp = await eliminarArticulo(id)
    if (resp.ok) {
      avisoExito(t('panelGestion.eliminado'))
      await recargarTodo()
    } else {
      avisoError(t('panelGestion.errorGuardar'))
    }
  }

  function alGuardado() {
    setFormulario(null)
    avisoExito(t('panelGestion.guardado'))
    void recargarTodo()
  }

  async function eliminarCategoriaHandler(id: string, nombre: string) {
    if (!window.confirm(t('panelCategorias.confirmarEliminar', { nombre }))) return
    const resp = await eliminarCategoria(id)
    if (resp.ok) {
      avisoExito(t('panelCategorias.eliminado'))
      await cargarCategorias()
      router.refresh() // el contenido público refleja la categoría borrada
    } else if (resp.status === 409) {
      // Bloqueo por integridad: la categoría aún tiene artículos asignados.
      avisoError(t('panelCategorias.errorConArticulos'))
    } else if (resp.status === 401) {
      router.replace(rutas.login(idioma))
    } else {
      avisoError(t('panelCategorias.errorGuardar'))
    }
  }

  function alGuardadoCategoria(modo: 'crear' | 'editar') {
    setFormCategoria(null)
    avisoExito(modo === 'crear' ? t('panelCategorias.creado') : t('panelCategorias.guardado'))
    void cargarCategorias()
    router.refresh() // el contenido público refleja la categoría creada/editada
  }

  const filas = filtro === 'todas' ? preguntas : preguntas.filter(p => p.estado === filtro)

  const columnas = ['pregunta', 'veces', 'similitud', 'fecha', 'estado', 'accion'] as const
  const alineacion: Record<(typeof columnas)[number], string> = {
    pregunta: 'text-left', veces: 'text-right', similitud: 'text-right', fecha: 'text-left', estado: 'text-left', accion: 'text-left',
  }

  // ── Contenido de la pestaña «Preguntas sin resolver» ─────────────────────────
  const contenidoSinResolver = (
    <div className="space-y-8">
      <p className="text-slate-600 text-sm">{t('panel.subtitulo')}</p>

      <section aria-labelledby="metrics-h2">
        <h2 id="metrics-h2" className="sr-only">
          {t('panel.metricasAria')}
        </h2>
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {contenido.metricas.map(metrica => {
            const { icono, fondo } = ICONO_METRICA[metrica.clave]
            const termino = t(`panel.metricas.${metrica.clave}`)
            return (
              <div key={metrica.clave} className="bg-white border border-slate-200 rounded-2xl p-5 flex items-start gap-4">
                <div className={`shrink-0 w-12 h-12 rounded-xl flex items-center justify-center ${fondo}`}>{icono}</div>
                <div>
                  <dt className="text-xs font-semibold text-slate-600 uppercase tracking-wide leading-snug">{termino}</dt>
                  <dd className="text-3xl font-bold text-slate-900 mt-1 leading-none">
                    <span className="sr-only">{`${metrica.valor} — ${termino}`}</span>
                    <span aria-hidden="true">{metrica.valor}</span>
                  </dd>
                  <p className="text-xs text-slate-500 mt-1">{t(`panel.metricas.${metrica.clave}Sub`)}</p>
                </div>
              </div>
            )
          })}
        </dl>
      </section>

      <div className="flex items-center gap-3 flex-wrap">
        <span id="filtro-etiqueta" className="text-sm font-medium text-slate-700">
          {t('panel.filtrar')}
        </span>
        <div className="flex items-center gap-2 flex-wrap" role="group" aria-labelledby="filtro-etiqueta">
          {FILTROS.map(valor => {
            const activo = filtro === valor
            return (
              <button
                key={valor}
                type="button"
                onClick={() => setFiltro(valor)}
                aria-pressed={activo}
                className={`px-3 rounded-full text-xs font-semibold border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] ${
                  activo
                    ? 'bg-[var(--acento)] text-white border-[var(--acento)]'
                    : 'bg-white text-slate-700 border-slate-500 hover:border-[var(--acento)] hover:text-[var(--acento)]'
                }`}
              >
                {valor === 'todas' ? t('panel.filtroTodas') : t(`kcs.${valor}`)}
              </button>
            )
          })}
        </div>
      </div>

      <section aria-labelledby="table-h2">
        <h2 id="table-h2" className="sr-only">
          {t('panel.tablaTitulo')}
        </h2>
        <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label={t('panel.tablaAria')}>
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50">
                  {columnas.map(columna => (
                    <th
                      key={columna}
                      scope="col"
                      className={`px-4 py-3 text-xs font-bold text-slate-600 uppercase tracking-wider whitespace-nowrap ${alineacion[columna]}`}
                    >
                      {t(`panel.columnas.${columna}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {filas.map(fila => {
                  const porcentaje = Math.round(fila.similitud * 100)
                  const fecha = fechaLegible(fila.fecha, i18n.language)
                  return (
                    <tr key={fila.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3.5 text-slate-800 font-medium max-w-[280px]">
                        <span className="leading-snug">{fila.pregunta}</span>
                      </td>
                      <td className="px-4 py-3.5 text-right tabular-nums">
                        <span className="font-semibold text-slate-900">{fila.veces}</span>
                      </td>
                      <td className="px-4 py-3.5 text-right tabular-nums">
                        <span
                          className={`font-semibold ${
                            fila.similitud >= 0.8 ? 'text-emerald-800' : fila.similitud >= 0.6 ? 'text-amber-800' : 'text-slate-600'
                          }`}
                        >
                          <span className="sr-only">{t('panel.similitudAria', { porcentaje })}</span>
                          <span aria-hidden="true">{porcentaje} %</span>
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-slate-600 whitespace-nowrap text-xs">
                        <time dateTime={fila.fecha}>{fecha}</time>
                      </td>
                      <td className="px-4 py-3.5">
                        <KcsChip estado={fila.estado} />
                      </td>
                      <td className="px-4 py-3.5">
                        {fila.estado !== 'cubierta' ? (
                          <button
                            type="button"
                            onClick={() => {
                              setFormulario({ modo: 'crear', preguntaId: fila.id })
                              setAviso(null)
                            }}
                            aria-label={t('panel.crearArticuloAria', { pregunta: fila.pregunta })}
                            className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-[var(--acento-claro)] text-[var(--acento)] bg-[var(--acento-claro)] hover:bg-[var(--acento-claro)] hover:border-[var(--acento)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px] whitespace-nowrap"
                          >
                            <Ic.Plus size={13} />
                            {t('panel.crearArticulo')}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-600 italic">{t('panel.articuloExistente')}</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="px-4 py-3 border-t border-slate-200 text-xs text-slate-600 bg-slate-50/50">
            {t('panel.mostrando', { visibles: filas.length, total: preguntas.length })}
          </div>
        </div>
      </section>
    </div>
  )

  // ── Contenido de la pestaña «Gestión de artículos» ───────────────────────────
  const contenidoGestion = (
    <section aria-labelledby="gestion-h2" className="space-y-4">
      <h2 id="gestion-h2" className="sr-only">
        {t('panelGestion.titulo')}
      </h2>
      <div className="flex items-center justify-end gap-4 flex-wrap">
        <button
          type="button"
          onClick={() => {
            setFormulario({ modo: 'crear' })
            setAviso(null)
          }}
          className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
          style={{ background: 'var(--acento)' }}
        >
          <Ic.Plus size={15} />
          {t('panelGestion.nuevo')}
        </button>
      </div>

      <ul className="rounded-2xl border border-slate-200 bg-white divide-y divide-slate-200 list-none p-0 m-0">
        {contenido.articulos.map(articulo => (
          <li key={articulo.id} className="flex items-center justify-between gap-3 px-4 py-3 flex-wrap">
            <span className="text-sm font-medium text-slate-800">{articulo.titulo}</span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => abrirEditar(articulo.id)}
                aria-label={t('panelGestion.editarAria', { titulo: articulo.titulo })}
                className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-slate-500 text-slate-700 bg-white hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
              >
                <Ic.Edit size={14} />
                {t('panelGestion.editar')}
              </button>
              <button
                type="button"
                onClick={() => eliminar(articulo.id, articulo.titulo)}
                aria-label={t('panelGestion.eliminarAria', { titulo: articulo.titulo })}
                className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-red-200 text-red-800 bg-red-50 hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
              >
                <Ic.Trash size={14} />
                {t('panelGestion.eliminar')}
              </button>
            </div>
          </li>
        ))}
      </ul>

      {formulario && (
        <Modal labelledBy="form-articulo-h" onCerrar={() => setFormulario(null)} cerrarAlClicarFondo={false}>
          <ArticuloForm
            categorias={contenido.categorias}
            modo={formulario.modo}
            inicial={formulario.inicial}
            preguntaId={formulario.preguntaId}
            onCerrar={() => setFormulario(null)}
            onGuardado={alGuardado}
          />
        </Modal>
      )}
    </section>
  )

  // ── Contenido de la pestaña «Categorías» (Editor + Administrador) ────────────
  const contenidoCategorias = (
    <section aria-labelledby="categorias-h2" className="space-y-4">
      <h2 id="categorias-h2" className="sr-only">
        {t('panelCategorias.titulo')}
      </h2>
      <div className="flex items-center justify-end gap-4 flex-wrap">
        <button
          type="button"
          onClick={() => {
            setFormCategoria({ modo: 'crear' })
            setAviso(null)
          }}
          className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
          style={{ background: 'var(--acento)' }}
        >
          <Ic.Plus size={15} />
          {t('panelCategorias.nuevo')}
        </button>
      </div>

      {categorias.length === 0 ? (
        <p className="text-sm text-slate-600">{t('panelCategorias.vacio')}</p>
      ) : (
        <ul className="rounded-2xl border border-slate-200 bg-white divide-y divide-slate-200 list-none p-0 m-0">
          {categorias.map(categoria => (
            <li key={categoria.id} className="flex items-center justify-between gap-3 px-4 py-3 flex-wrap">
              <span className="text-sm font-medium text-slate-800">
                {categoria[idioma].nombre}
                <span className="text-slate-400 font-normal"> · {categoria.id}</span>
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setFormCategoria({ modo: 'editar', inicial: categoria })
                    setAviso(null)
                  }}
                  aria-label={t('panelCategorias.editarAria', { nombre: categoria[idioma].nombre })}
                  className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-slate-500 text-slate-700 bg-white hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                >
                  <Ic.Edit size={14} />
                  {t('panelCategorias.editar')}
                </button>
                <button
                  type="button"
                  onClick={() => eliminarCategoriaHandler(categoria.id, categoria[idioma].nombre)}
                  aria-label={t('panelCategorias.eliminarAria', { nombre: categoria[idioma].nombre })}
                  className="inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-red-200 text-red-800 bg-red-50 hover:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                >
                  <Ic.Trash size={14} />
                  {t('panelCategorias.eliminar')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {formCategoria && (
        <Modal labelledBy="form-categoria-h" onCerrar={() => setFormCategoria(null)} cerrarAlClicarFondo={false}>
          <CategoriaForm
            modo={formCategoria.modo}
            inicial={formCategoria.inicial}
            onCerrar={() => setFormCategoria(null)}
            onGuardado={alGuardadoCategoria}
          />
        </Modal>
      )}
    </section>
  )

  // Vista previa de contraste en cliente (adelanta el aviso; la autoridad es el
  // servidor). El banner se deriva del acento, igual que en el servidor, así que el
  // aviso ya solo puede objetar el acento. El `<input type=color>` siempre da `#rrggbb`
  // válido, así que no lanza.
  const banner = derivarDegradadoBanner(acento)
  const falloPaleta = validarPaleta(acento, banner.desde, banner.medio, banner.hasta)
  const tokensAcento = derivarTokensAcento(acento)

  // ── Contenido de la pestaña «Administración» (solo Administrador) ────────────
  const contenidoAdmin = (
    <section aria-labelledby="admin-h2" className="space-y-4">
      <h2 id="admin-h2" className="sr-only">
        {t('panel.seccionAdmin')}
      </h2>

      <form onSubmit={guardarEmpresaHandler} className="rounded-2xl border border-slate-200 bg-white p-5 space-y-3" aria-labelledby="empresa-h3">
        <h3 id="empresa-h3" className="text-sm font-semibold text-slate-900">
          {t('ajustesEmpresa.titulo')}
        </h3>
        <div className="flex items-end gap-2 flex-wrap">
          <input
            id="campo-empresa"
            type="text"
            required
            value={empresaInput}
            onChange={e => setEmpresaInput(e.target.value)}
            aria-labelledby="empresa-h3"
            aria-describedby="empresa-ayuda"
            className="flex-1 min-w-[16rem] px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          />
          <button
            type="submit"
            className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
            style={{ background: 'var(--acento)' }}
          >
            <Ic.Save size={15} />
            {t('ajustesEmpresa.guardar')}
          </button>
        </div>
        <p id="empresa-ayuda" className="text-xs text-slate-500">
          {t('ajustesEmpresa.ayuda')}
        </p>
      </form>

      <form onSubmit={guardarMarcaHandler} className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" aria-labelledby="marca-h3">
        <h3 id="marca-h3" className="text-sm font-semibold text-slate-900">
          {t('ajustesMarca.titulo')}
        </h3>

        <div>
          <label htmlFor="marca-acento" className="block text-sm font-medium text-slate-700 mb-1">
            {t('ajustesMarca.acento')}
          </label>
          <div className="flex items-center gap-2">
            <input
              id="marca-acento"
              type="color"
              value={acento}
              onChange={e => setAcento(e.target.value)}
              className="w-11 h-11 rounded-lg border border-slate-400 bg-white p-0.5 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1"
            />
            <span className="text-sm text-slate-600 font-mono">{acento}</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">{t('ajustesMarca.bannerAyuda')}</p>
        </div>

        {/* Vista previa en vivo: botón, degradado del banner (derivado) y anillo de foco. */}
        <div className="rounded-xl border border-slate-200 p-4 space-y-3" aria-hidden="true">
          <div
            className="rounded-lg h-16 flex items-center justify-center px-4 text-white text-lg font-bold text-center"
            style={{
              background: `linear-gradient(160deg, ${banner.desde} 0%, ${banner.medio} 60%, ${banner.hasta} 100%)`,
              fontFamily: 'var(--font-serif), serif',
            }}
          >
            {t('inicio.titulo', { empresa: contenido.empresa })}
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="inline-flex items-center px-4 py-2 rounded-lg text-white text-sm font-semibold" style={{ background: acento }}>
              {t('ajustesMarca.previewBoton')}
            </span>
            <span
              className="inline-flex items-center px-4 py-2 rounded-lg text-sm font-semibold bg-white"
              style={{ color: acento, outline: `2px solid ${tokensAcento.foco}`, outlineOffset: 2 }}
            >
              {t('ajustesMarca.previewFoco')}
            </span>
          </div>
        </div>

        {/* Aviso de contraste (adelanto en cliente; el servidor decide al guardar). */}
        <div role="status" aria-live="polite" className="min-h-[1.25rem]">
          {falloPaleta ? (
            <p className="inline-flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
              <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
              {t('ajustesMarca.errorContrastePar', {
                par: falloPaleta.par,
                ratio: falloPaleta.ratio,
                minimo: falloPaleta.minimo,
              })}
            </p>
          ) : (
            <p className="inline-flex items-center gap-2 text-sm text-emerald-800">
              <Ic.CheckCircle size={15} className="text-emerald-700 shrink-0" />
              {t('ajustesMarca.contrasteOk')}
            </p>
          )}
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={!!falloPaleta}
            className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px] disabled:opacity-60"
            style={{ background: 'var(--acento)' }}
          >
            <Ic.Save size={15} />
            {t('ajustesMarca.guardar')}
          </button>
        </div>
      </form>

      {/* Subida de logotipo (PNG/ICO/JPEG). La valida el servidor por magic bytes. */}
      <form className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" aria-labelledby="logo-h3">
        <div className="flex items-start gap-3">
          <div>
            <h3 id="logo-h3" className="text-sm font-semibold text-slate-900">
              {t('ajustesMarca.logo')}
            </h3>
            <p id="marca-logo-ayuda" className="text-xs text-slate-500 mt-0.5">
              {t('ajustesMarca.logoAyuda')}
            </p>
          </div>
        </div>

        <div className="border-t border-slate-200 pt-4 flex items-center gap-4 flex-wrap">
          {contenido.logo ? (
            // eslint-disable-next-line @next/next/no-img-element -- binario servido por la API
            <img
              src={contenido.logoVersion ? `/api/marca/logo?v=${contenido.logoVersion}` : '/api/marca/logo'}
              alt={t('ajustesMarca.logoActualAlt')}
              className="w-14 h-14 rounded-lg object-contain border border-slate-200 shrink-0"
            />
          ) : (
            <span className="w-14 h-14 rounded-lg border border-dashed border-slate-300 flex items-center justify-center text-slate-400 shrink-0" aria-hidden="true">
              <Ic.Image size={20} />
            </span>
          )}
          <div className="flex items-center gap-3 flex-wrap">
            {/* El input queda accesible por teclado (sr-only, no display:none); el
                foco se refleja con focus-within sobre la etiqueta que actúa de botón. */}
            <label className="inline-flex items-center gap-2 px-4 rounded-lg border bg-white text-sm font-semibold cursor-pointer hover:bg-slate-50 min-h-[44px] focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-[var(--acento-foco)]" style={{ color: 'var(--acento)', borderColor: 'var(--acento)' }}>
              <Ic.Upload size={15} />
              {t('ajustesMarca.logoBoton')}
              <input
                type="file"
                accept="image/png,image/x-icon,image/jpeg,.png,.ico,.jpg,.jpeg"
                disabled={subiendoLogo}
                onChange={e => {
                  const archivo = e.target.files?.[0]
                  if (archivo) void subirLogoHandler(archivo)
                  e.target.value = '' // permite volver a elegir el mismo archivo
                }}
                aria-label={t('ajustesMarca.logo')}
                aria-describedby="marca-logo-ayuda"
                className="sr-only"
              />
            </label>
          </div>
        </div>
      </form>

      {/* Plantilla del sitio público del portal. Afecta solo al sitio público; el panel
          interno conserva su aspecto con cualquiera de las dos. */}
      <form
        onSubmit={guardarPlantillaHandler}
        className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"
        aria-labelledby="plantilla-h3"
      >
        <div>
          <h3 id="plantilla-h3" className="text-sm font-semibold text-slate-900">
            {t('ajustesPlantilla.titulo')}
          </h3>
          <p id="plantilla-ayuda" className="text-xs text-slate-500 mt-0.5">
            {t('ajustesPlantilla.ayuda')}
          </p>
        </div>

        {/* `mt-0 mx-0` y no `m-0`: en Tailwind v4 el `space-y-4` del formulario separa con
            margen inferior, y `m-0` lo anulaba (el botón quedaba pegado a las opciones). */}
        <fieldset className="space-y-3 border-0 p-0 mt-0 mx-0" aria-describedby="plantilla-ayuda">
          <legend className="sr-only">{t('ajustesPlantilla.titulo')}</legend>
          {PLANTILLAS.map(opcion => {
            const elegida = plantillaInput === opcion
            const activa = plantillaGuardada === opcion
            return (
              <label
                key={opcion}
                className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer min-h-[44px] focus-within:ring-2 focus-within:ring-[var(--acento-foco)] focus-within:ring-offset-1 ${
                  elegida ? 'border-[var(--acento)] bg-[var(--acento-claro)]' : 'border-slate-200 hover:bg-slate-50'
                }`}
              >
                <input
                  type="radio"
                  name="plantilla"
                  value={opcion}
                  checked={elegida}
                  onChange={() => setPlantillaInput(opcion)}
                  className="mt-1 w-4 h-4 shrink-0"
                  style={{ accentColor: 'var(--acento)' }}
                />
                <span>
                  <span className="flex items-center gap-2 flex-wrap text-sm font-semibold text-slate-900">
                    {t(`ajustesPlantilla.opcion.${opcion}`)}
                    {activa && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium text-white" style={{ background: 'var(--acento)' }}>
                        <Ic.CheckCircle size={12} />
                        {t('ajustesPlantilla.activa')}
                      </span>
                    )}
                  </span>
                  <span className="block text-xs text-slate-600 mt-1">
                    {t(`ajustesPlantilla.descripcion.${opcion}`)}
                  </span>
                </span>
              </label>
            )
          })}
        </fieldset>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={guardandoPlantilla}
            className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
            style={{ background: 'var(--acento)' }}
          >
            <Ic.Save size={15} />
            {t('ajustesPlantilla.guardar')}
          </button>
        </div>
      </form>

      {/* Enlace de GitHub del portal: la plantilla de documentación muestra el icono en la
          cabecera solo si hay URL. El servidor admite solo https://github.com/… (422). */}
      <form
        onSubmit={guardarGithubHandler}
        className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4"
        aria-labelledby="github-h3"
        noValidate
      >
        <div>
          <h3 id="github-h3" className="text-sm font-semibold text-slate-900">
            {t('ajustesGithub.titulo')}
          </h3>
          <p id="github-ayuda" className="text-xs text-slate-500 mt-0.5">
            {t('ajustesGithub.ayuda')}
          </p>
        </div>
        <div>
          <label htmlFor="github-url" className="block text-sm font-medium text-slate-700 mb-1">
            {t('ajustesGithub.etiqueta')}
          </label>
          <input
            id="github-url"
            type="url"
            inputMode="url"
            value={githubInput}
            onChange={e => setGithubInput(e.target.value)}
            placeholder="https://github.com/organizacion/repositorio"
            aria-describedby={errorGithub ? 'github-ayuda github-error' : 'github-ayuda'}
            aria-invalid={errorGithub ? true : undefined}
            maxLength={300}
            className="w-full min-h-[44px] px-3 py-2 rounded-lg border border-slate-500 bg-white text-slate-900 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:border-transparent"
          />
          {errorGithub && (
            <p id="github-error" role="alert" className="flex items-center gap-1.5 text-sm text-rose-700 mt-1.5">
              <Ic.AlertCircle size={14} className="shrink-0" />
              {errorGithub}
            </p>
          )}
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={guardandoGithub}
            className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
            style={{ background: 'var(--acento)' }}
          >
            <Ic.Save size={15} />
            {t('ajustesGithub.guardar')}
          </button>
        </div>
      </form>

      {puedeConfigurarIA && (
      <section className="rounded-2xl border border-slate-200 bg-white p-5 space-y-4" aria-labelledby="config-ia-h3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="config-ia-h3" className="text-sm font-semibold text-slate-900">
            {t('configIA.titulo')}
          </h3>
          <button
            type="button"
            onClick={() => void comprobarSaludHandler()}
            disabled={comprobandoSalud}
            aria-describedby="config-ia-salud-ayuda"
            className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-400 bg-white text-slate-800 text-sm font-semibold hover:bg-slate-50 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
          >
            <Ic.RefreshCw size={15} />
            {comprobandoSalud ? t('configIA.salud.comprobando') : t('configIA.salud.comprobar')}
          </button>
        </div>
        <p id="config-ia-salud-ayuda" className="text-xs text-slate-600">
          {t('configIA.salud.ayuda')}
        </p>
        {!configIA && <p className="text-xs text-slate-500">{t('configIA.cargando')}</p>}
        {configIA && (['chat', 'traduccion', 'embeddings'] as const).map(rol => {
          const est = estadoDe(rol)
          return (
            <form
              key={rol}
              onSubmit={e => guardarRolHandler(rol, e)}
              className="space-y-2 border-t border-slate-100 pt-4 first:border-t-0 first:pt-0"
              aria-labelledby={`config-ia-${rol}-h4`}
            >
              <h4 id={`config-ia-${rol}-h4`} className="text-sm font-semibold text-slate-800">
                {t(`configIA.${rol}.titulo`)}
              </h4>
              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label htmlFor={`config-ia-${rol}-proveedor`} className="block text-sm font-medium text-slate-700 mb-1">
                    {t('configIA.proveedor')}
                  </label>
                  <select
                    id={`config-ia-${rol}-proveedor`}
                    value={est.seleccionado}
                    onChange={e => seleccionarProveedor(rol, e.target.value)}
                    className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                  >
                    {est.proveedores.map(id => (
                      <option key={id} value={id}>
                        {t(`configIA.proveedores.${id}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor={`config-ia-${rol}-clave`} className="block text-sm font-medium text-slate-700 mb-1">
                    {t('configIA.clave')}
                  </label>
                  {est.editando ? (
                    <input
                      id={`config-ia-${rol}-clave`}
                      type="password"
                      value={claveInput[rol]}
                      onChange={e => setClaveInput(prev => ({ ...prev, [rol]: e.target.value }))}
                      autoComplete="off"
                      placeholder={t('configIA.clavePlaceholder')}
                      aria-describedby={`config-ia-${rol}-estado`}
                      className="w-full px-3 py-2.5 rounded-lg border border-slate-400 text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                    />
                  ) : (
                    <input
                      id={`config-ia-${rol}-clave`}
                      type="text"
                      readOnly
                      value={est.pista ? `••••${est.pista}` : '••••••••'}
                      aria-label={
                        est.pista
                          ? t('configIA.claveTerminaEn', { fin: est.pista })
                          : t('configIA.claveConfiguradaAria')
                      }
                      aria-describedby={`config-ia-${rol}-estado`}
                      className="w-full px-3 py-2.5 rounded-lg border border-slate-300 bg-slate-50 text-slate-600 font-mono tracking-wider focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
                    />
                  )}
                </div>
              </div>
              <p id={`config-ia-${rol}-estado`} className="text-xs text-slate-600 inline-flex items-center gap-1">
                {est.configurada ? (
                  <Ic.CheckCircle size={13} className="text-emerald-700" />
                ) : (
                  <Ic.AlertCircle size={13} className="text-slate-500" />
                )}
                {est.configurada
                  ? t('configIA.estadoConfigurada', {
                      proveedor: t(`configIA.proveedores.${est.seleccionado}`),
                    })
                  : t('configIA.estadoSinConfigurar', {
                      proveedor: t(`configIA.proveedores.${est.seleccionado}`),
                    })}
              </p>
              {saludIA?.[rol] && (() => {
                const salud = saludIA[rol]
                const { Icono, clase } = SALUD_PRESENTACION[salud.estado]
                return (
                  <p
                    className="text-xs text-slate-700 flex items-start gap-1.5"
                    // `status`: el resultado llega tras pulsar «Comprobar», así que
                    // un lector de pantalla debe anunciarlo sin robar el foco.
                    role="status"
                  >
                    <Icono size={13} className={`${clase} mt-0.5 shrink-0`} />
                    <span>
                      {/* La etiqueta de texto es la que porta el estado; el icono y
                          el color solo lo refuerzan (WCAG 1.4.1). */}
                      <strong className="font-semibold">
                        {t(`configIA.salud.estados.${salud.estado}`)}
                      </strong>
                      {' — '}
                      {salud.detalle}
                    </span>
                  </p>
                )
              })()}
              <div className="flex flex-wrap gap-2 justify-end">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
                  style={{ background: 'var(--acento)' }}
                >
                  <Ic.Save size={15} />
                  {t('configIA.guardar')}
                </button>
                {est.configurada &&
                  (editandoClave[rol] ? (
                    <button
                      type="button"
                      onClick={() => {
                        setEditandoClave(prev => ({ ...prev, [rol]: false }))
                        setClaveInput(prev => ({ ...prev, [rol]: '' }))
                      }}
                      className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-400 bg-white text-slate-800 text-sm font-semibold hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
                    >
                      <Ic.X size={15} />
                      {t('configIA.cancelar')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setEditandoClave(prev => ({ ...prev, [rol]: true }))
                        setClaveInput(prev => ({ ...prev, [rol]: '' }))
                      }}
                      className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-400 bg-white text-slate-800 text-sm font-semibold hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
                    >
                      <Ic.Edit size={15} />
                      {t('configIA.editar')}
                    </button>
                  ))}
                {est.configurada && (
                  <button
                    type="button"
                    onClick={() => setConfirmarBorrado({ rol, proveedor: est.seleccionado })}
                    className="inline-flex items-center gap-2 px-4 rounded-lg border border-rose-400 bg-white text-rose-700 text-sm font-semibold hover:bg-rose-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-rose-500 min-h-[44px]"
                  >
                    <Ic.Trash size={15} />
                    {t('configIA.eliminar')}
                  </button>
                )}
              </div>
            </form>
          )
        })}
        <p className="text-xs text-slate-500">{t('configIA.ayuda')}</p>
        {confirmarBorrado && (
          <Modal labelledBy="config-ia-borrar-h" onCerrar={() => setConfirmarBorrado(null)}>
            <div className="rounded-2xl bg-white p-5 shadow-xl">
              <h4 id="config-ia-borrar-h" className="text-sm font-semibold text-slate-900">
                {t('configIA.eliminarConfirmacion.titulo')}
              </h4>
              <p className="mt-2 text-sm text-slate-700">
                {t('configIA.eliminarConfirmacion.texto', {
                  proveedor: t(`configIA.proveedores.${confirmarBorrado.proveedor}`),
                })}
              </p>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setConfirmarBorrado(null)}
                  className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-400 bg-white text-slate-800 text-sm font-semibold hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] min-h-[44px]"
                >
                  {t('configIA.cancelar')}
                </button>
                <button
                  type="button"
                  onClick={confirmarBorradoClaveHandler}
                  className="inline-flex items-center gap-2 px-4 rounded-lg bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-rose-500 min-h-[44px]"
                >
                  <Ic.Trash size={15} />
                  {t('configIA.eliminar')}
                </button>
              </div>
            </div>
          </Modal>
        )}
      </section>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <Link
          href={rutas.usuarios(idioma)}
          className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
        >
          <Ic.User size={15} />
          {t('gestionUsuarios.enlace')}
        </Link>
        <Link
          href={rutas.documentos(idioma)}
          className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
        >
          <Ic.FileText size={15} />
          {t('gestionDocumentos.enlace')}
        </Link>
        {esSuperAdmin(nivel) && (
          <Link
            href={rutas.portales(idioma)}
            className="inline-flex items-center gap-2 px-4 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]"
          >
            <Ic.Shield size={15} />
            {t('gestionPortales.enlace')}
          </Link>
        )}
      </div>
    </section>
  )

  // La pestaña «Chats» monta su propio Client Component: hace fetch al BFF
  // (`/api/admin/chats*`) al abrirse y no depende del contenido servido, así
  // que se renderiza incluso si el resto del panel no lo necesita.
  const contenidoChats = <PanelChats idioma={idioma} />

  // Igual que «Chats»: monta su propio Client Component con fetch al BFF
  // (`/api/admin/sugerencias*`); necesita las categorías para precargar el
  // `ArticuloForm` al abrir una sugerencia con la misma categoría por defecto
  // que «Nuevo artículo».
  const contenidoSugerencias = <PanelSugerencias idioma={idioma} categorias={contenido.categorias} />

  const pestanas: Pestana<PestanaId>[] = [
    { id: 'sinResolver', etiqueta: t('panel.titulo'), contenido: contenidoSinResolver },
    { id: 'gestion', etiqueta: t('panelGestion.titulo'), contenido: contenidoGestion },
    { id: 'chats', etiqueta: t('panelChats.titulo'), contenido: contenidoChats },
    { id: 'sugerencias', etiqueta: t('panelSugerencias.titulo'), contenido: contenidoSugerencias },
    { id: 'categorias', etiqueta: t('panelCategorias.titulo'), contenido: contenidoCategorias },
  ]
  if (puedeAdministrar) {
    pestanas.push({ id: 'admin', etiqueta: t('panel.seccionAdmin'), contenido: contenidoAdmin })
  }

  return (
    <main id="main-content" tabIndex={-1} className="focus:outline-none">
      <div className="border-b border-slate-200 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-[var(--acento)] uppercase tracking-widest mb-1">
              <Ic.BarChart size={14} />
              {t('panel.seccion')}
            </div>
            <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'var(--font-serif), serif' }}>
              {t('panel.tituloGeneral')}
            </h1>
          </div>
          <button
            type="button"
            onClick={cerrarSesion}
            className="inline-flex items-center gap-2 px-3 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px] self-start"
          >
            <Ic.LogOut size={15} />
            {t('panel.cerrarSesion')}
          </button>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        <div
          role={aviso?.tono === 'error' ? 'alert' : 'status'}
          aria-live={aviso?.tono === 'error' ? 'assertive' : 'polite'}
          className="min-h-[1.5rem] mb-6"
        >
          {aviso && (
            <p
              className={`inline-flex items-center gap-2 text-sm px-3 py-2 rounded-lg border ${
                aviso.tono === 'error'
                  ? 'text-red-800 bg-red-50 border-red-200'
                  : 'text-emerald-800 bg-emerald-50 border-emerald-200'
              }`}
            >
              {aviso.tono === 'error' ? (
                <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
              ) : (
                <Ic.CheckCircle size={15} className="text-emerald-700 shrink-0" />
              )}
              {aviso.texto}
            </p>
          )}
        </div>

        <Tabs pestanas={pestanas} activa={pestanaActiva} onCambio={cambiarPestana} etiquetaLista={t('panel.tabsAria')} />
      </div>
    </main>
  )
}
