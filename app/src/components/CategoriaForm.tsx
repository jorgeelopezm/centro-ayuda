import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { IDIOMAS, type Idioma, type NombreIcono } from '@/types'
import { guardarCategoria, traducirCategoria, type CategoriaAdmin, type TraduccionCategoriaAdmin } from '@/data/admin'
import { derivarId, derivarSlug } from '@/data/slug'
import { Ic, Icono } from '@/components/iconos'
import { Tabs, type Pestana } from './Tabs'

type Modo = 'crear' | 'editar'

// Utilidades de campo comunes, ya sobre los tokens de acento (foco tokenizado).
const CAMPO =
  'w-full min-h-[44px] px-3 py-2 rounded-lg border border-slate-500 bg-white text-slate-900 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:border-transparent'
const CAMPO_RO =
  'w-full min-h-[44px] px-3 py-2 rounded-lg border border-slate-300 bg-slate-100 text-slate-600 text-sm'
const BOTON_SEC =
  'inline-flex items-center gap-1.5 px-3 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]'

// Conjunto cerrado de iconos que el frontend sabe renderizar (`iconos.tsx`). El
// servidor valida el mismo conjunto (`IconoCategoria` en `schemas.py`). La clave de
// i18n de cada etiqueta va en `panelCategorias.icono<Nombre>` (p. ej. `iconoUsuario`).
// Se agrupan en el selector (`<optgroup>`); «Sin icono» es la opción vacía (`null`).
const GRUPOS_ICONOS: { grupo: string; iconos: { nombre: NombreIcono; clave: string }[] }[] = [
  {
    grupo: 'grupoGeneral',
    iconos: [
      { nombre: 'usuario', clave: 'iconoUsuario' },
      { nombre: 'tarjeta', clave: 'iconoTarjeta' },
      { nombre: 'paquete', clave: 'iconoPaquete' },
      { nombre: 'devolver', clave: 'iconoDevolver' },
      { nombre: 'escudo', clave: 'iconoEscudo' },
      { nombre: 'documento', clave: 'iconoDocumento' },
    ],
  },
  {
    grupo: 'grupoDesarrollo',
    iconos: [
      { nombre: 'codigo', clave: 'iconoCodigo' },
      { nombre: 'terminal', clave: 'iconoTerminal' },
      { nombre: 'git', clave: 'iconoGit' },
      { nombre: 'base-datos', clave: 'iconoBaseDatos' },
      { nombre: 'servidor', clave: 'iconoServidor' },
      { nombre: 'nube', clave: 'iconoNube' },
      { nombre: 'api', clave: 'iconoApi' },
      { nombre: 'bug', clave: 'iconoBug' },
      { nombre: 'llave', clave: 'iconoLlave' },
      { nombre: 'cpu', clave: 'iconoCpu' },
      { nombre: 'libro', clave: 'iconoLibro' },
      { nombre: 'cohete', clave: 'iconoCohete' },
    ],
  },
]

type TradDraft = { nombre: string; slug: string }
type Draft = {
  id: string
  icono: NombreIcono | null
  orden: number
  es: TradDraft
  pt: TradDraft
}

function draftInicial(inicial?: CategoriaAdmin): Draft {
  if (inicial) {
    return {
      id: inicial.id,
      icono: inicial.icono,
      orden: inicial.orden,
      es: { nombre: inicial.es.nombre, slug: inicial.es.slug },
      pt: { nombre: inicial.pt.nombre, slug: inicial.pt.slug },
    }
  }
  return {
    id: '',
    icono: GRUPOS_ICONOS[0].iconos[0].nombre,
    orden: 0,
    es: { nombre: '', slug: '' },
    pt: { nombre: '', slug: '' },
  }
}

/**
 * Alta y edición de una categoría bilingüe. Espeja `ArticuloForm`/`UsuarioForm`:
 * es+pt obligatorios (atómico), id y slugs autogenerados del nombre mientras no se
 * editen a mano, id bloqueado al editar (es la clave estable), pestañas por idioma
 * con traducción asistida por IA. El servidor normaliza id y slugs; el cliente solo
 * adelanta la vista.
 */
export function CategoriaForm({
  modo,
  inicial,
  onCerrar,
  onGuardado,
}: {
  modo: Modo
  inicial?: CategoriaAdmin
  onCerrar: () => void
  onGuardado: (modo: Modo) => void
}) {
  const { t, i18n } = useTranslation()
  const idiomaInterfaz: Idioma = i18n.language === 'pt' ? 'pt' : 'es'
  const [idiomaActivo, setIdiomaActivo] = useState<Idioma>(() => idiomaInterfaz)
  const [draft, setDraft] = useState<Draft>(() => draftInicial(inicial))
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [traduciendo, setTraduciendo] = useState<Idioma | null>(null)
  const [avisoTrad, setAvisoTrad] = useState<string | null>(null)
  const [idEditado, setIdEditado] = useState(false)
  const [slugEditado, setSlugEditado] = useState<Record<Idioma, boolean>>({ es: false, pt: false })

  const patchTrad = (idioma: Idioma, patch: Partial<TradDraft>) =>
    setDraft(d => ({ ...d, [idioma]: { ...d[idioma], ...patch } }))

  function alCambiarNombre(idioma: Idioma, valor: string) {
    setDraft(d => {
      const nd: Draft = { ...d, [idioma]: { ...d[idioma], nombre: valor } }
      if (!slugEditado[idioma]) nd[idioma] = { ...nd[idioma], slug: derivarSlug(valor) }
      // El id (clave estable) sigue al nombre en español, solo al crear.
      if (idioma === 'es' && modo === 'crear' && !idEditado) nd.id = derivarId(valor)
      return nd
    })
  }

  function alCambiarSlug(idioma: Idioma, valor: string) {
    setSlugEditado(s => ({ ...s, [idioma]: true }))
    patchTrad(idioma, { slug: valor })
  }

  async function traducirDesde(origen: Idioma) {
    if (traduciendo !== null) return // ya hay una traducción en curso: no reentrar
    setError(null)
    setAvisoTrad(null)

    if (draft[origen].nombre.trim() === '') {
      setError(t('panelCategorias.faltaNombreTraducir', { idioma: t(`idioma.${origen}`) }))
      if (origen !== idiomaActivo) setIdiomaActivo(origen)
      requestAnimationFrame(() => document.getElementById(`${origen}-cat-nombre`)?.focus())
      return
    }

    setTraduciendo(origen)
    try {
      const contenido: TraduccionCategoriaAdmin = { slug: draft[origen].slug, nombre: draft[origen].nombre }
      const resp = await traducirCategoria(origen, contenido)
      if (!resp.ok) {
        setError(
          resp.status === 409
            ? t('panelCategorias.traduccionSinProveedor')
            : t('panelCategorias.traduccionError'),
        )
        return
      }
      const tr = (await resp.json()) as TraduccionCategoriaAdmin
      const destino: Idioma = origen === 'es' ? 'pt' : 'es'
      setDraft(d => ({
        ...d,
        [destino]: { nombre: tr.nombre, slug: slugEditado[destino] ? d[destino].slug : derivarSlug(tr.nombre) },
      }))
      setIdiomaActivo(destino)
      requestAnimationFrame(() => document.getElementById(`${destino}-cat-nombre`)?.focus())
      setAvisoTrad(t('panelCategorias.traduccionLista', { idioma: t(`idioma.${destino}`) }))
    } catch {
      setError(t('panelCategorias.errorRed'))
    } finally {
      setTraduciendo(null)
    }
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      const payload: CategoriaAdmin = {
        id: draft.id,
        icono: draft.icono,
        orden: draft.orden,
        es: { ...draft.es },
        pt: { ...draft.pt },
      }
      const destino =
        modo === 'crear'
          ? ({ tipo: 'crear' } as const)
          : ({ tipo: 'editar', categoriaId: inicial!.id } as const)
      const resp = await guardarCategoria(payload, destino)
      if (resp.ok) {
        onGuardado(modo)
        return
      }
      setError(resp.status === 409 ? t('panelCategorias.errorIdDuplicado') : t('panelCategorias.errorGuardar'))
    } catch {
      setError(t('panelCategorias.errorRed'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <section aria-labelledby="form-categoria-h" className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xl">
      <div className="flex items-start justify-between gap-3 mb-4">
        <h2 id="form-categoria-h" className="text-lg font-bold text-slate-900">
          {modo === 'crear' ? t('panelCategorias.nuevo') : t('panelCategorias.editar')}
        </h2>
        <button
          type="button"
          onClick={onCerrar}
          aria-label={t('panelCategorias.cerrar')}
          className="shrink-0 inline-flex items-center justify-center w-11 h-11 rounded-lg border border-slate-500 bg-white text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1"
        >
          <Ic.X size={18} />
        </button>
      </div>

      <form onSubmit={enviar} noValidate className="space-y-5">
        <div role="alert" aria-live="assertive" className="min-h-[1.25rem]">
          {error && (
            <p className="flex items-center gap-2 text-sm text-red-800 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">
              <Ic.AlertCircle size={15} className="text-red-700 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <div role="status" aria-live="polite" className="empty:hidden">
          {avisoTrad && (
            <p className="flex items-center gap-2 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-2 rounded-lg">
              <Ic.CheckCircle size={15} className="text-emerald-700 shrink-0" />
              {avisoTrad}
            </p>
          )}
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="cat-id" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelCategorias.id')}
            </label>
            <input
              id="cat-id"
              className={modo === 'editar' ? CAMPO_RO : CAMPO}
              value={draft.id}
              onChange={e => {
                setIdEditado(true)
                setDraft(d => ({ ...d, id: e.target.value }))
              }}
              disabled={modo === 'editar'}
              required
              aria-describedby="cat-id-ayuda"
            />
            <p id="cat-id-ayuda" className="text-xs text-slate-500 mt-1">
              {modo === 'editar' ? t('panelCategorias.idBloqueadoAyuda') : t('panelCategorias.idAutoAyuda')}
            </p>
          </div>
          <div>
            <label htmlFor="cat-orden" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelCategorias.orden')}
            </label>
            <input
              id="cat-orden"
              type="number"
              min={0}
              className={CAMPO}
              value={draft.orden}
              onChange={e => setDraft(d => ({ ...d, orden: Number(e.target.value) }))}
              aria-describedby="cat-orden-ayuda"
            />
            <p id="cat-orden-ayuda" className="text-xs text-slate-500 mt-1">
              {t('panelCategorias.ordenAyuda')}
            </p>
          </div>
          <div className="sm:col-span-2 flex items-end gap-3">
            <div className="flex-1">
              <label htmlFor="cat-icono" className="block text-sm font-medium text-slate-700 mb-1">
                {t('panelCategorias.icono')}
              </label>
              <select
                id="cat-icono"
                className={CAMPO}
                value={draft.icono ?? ''}
                onChange={e =>
                  setDraft(d => ({ ...d, icono: e.target.value === '' ? null : (e.target.value as NombreIcono) }))
                }
              >
                <option value="">{t('panelCategorias.sinIcono')}</option>
                {GRUPOS_ICONOS.map(({ grupo, iconos }) => (
                  <optgroup key={grupo} label={t(`panelCategorias.${grupo}`)}>
                    {iconos.map(({ nombre, clave }) => (
                      <option key={nombre} value={nombre}>
                        {t(`panelCategorias.${clave}`)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </div>
            {/* Vista previa; con «Sin icono» el recuadro queda vacío (la etiqueta del
                selector ya lo dice en texto). */}
            <div
              className="shrink-0 w-11 h-11 rounded-lg flex items-center justify-center bg-[var(--acento-claro)] text-[var(--acento)]"
              aria-hidden="true"
            >
              <Icono nombre={draft.icono} size={20} />
            </div>
          </div>
        </div>

        <Tabs
          activa={idiomaActivo}
          onCambio={setIdiomaActivo}
          etiquetaLista={t('panelCategorias.idiomasTablist')}
          pestanas={IDIOMAS.map(
            (idioma): Pestana<Idioma> => ({
              id: idioma,
              etiqueta: t(`idioma.${idioma}`),
              contenido: (
                <SeccionIdioma
                  idioma={idioma}
                  trad={draft[idioma]}
                  traduciendo={traduciendo}
                  onNombre={valor => alCambiarNombre(idioma, valor)}
                  onSlug={valor => alCambiarSlug(idioma, valor)}
                  onTraducir={() => traducirDesde(idioma)}
                />
              ),
            }),
          )}
        />

        <div className="flex items-center gap-3 flex-wrap pt-2 border-t border-slate-200">
          <button
            type="submit"
            disabled={enviando}
            className="inline-flex items-center gap-2 px-4 rounded-lg text-white text-sm font-semibold hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--acento-foco)] disabled:opacity-60 min-h-[44px]"
            style={{ background: 'var(--acento)' }}
          >
            {enviando ? <Ic.Loader size={16} className="animate-spin motion-reduce:animate-none" /> : <Ic.Save size={16} />}
            {enviando ? t('panelCategorias.guardando') : t('panelCategorias.guardar')}
          </button>
          <button type="button" onClick={onCerrar} className={BOTON_SEC}>
            <Ic.X size={15} />
            {t('panelCategorias.cancelar')}
          </button>
        </div>
      </form>
    </section>
  )
}

function SeccionIdioma({
  idioma,
  trad,
  traduciendo,
  onNombre,
  onSlug,
  onTraducir,
}: {
  idioma: Idioma
  trad: TradDraft
  traduciendo: Idioma | null
  onNombre: (valor: string) => void
  onSlug: (valor: string) => void
  onTraducir: () => void
}) {
  const { t } = useTranslation()
  const destino: Idioma = idioma === 'es' ? 'pt' : 'es'
  const traduciendoEste = traduciendo === idioma
  const ocupado = traduciendo !== null

  return (
    <fieldset className="rounded-xl border border-slate-200 p-4">
      <legend className="px-2 text-sm font-bold text-[var(--acento)] uppercase tracking-wide">{t(`idioma.${idioma}`)}</legend>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <button
            type="button"
            onClick={onTraducir}
            aria-disabled={ocupado}
            aria-busy={traduciendoEste}
            className={`inline-flex items-center gap-1.5 px-3 rounded-lg text-xs font-semibold border border-[var(--acento-claro)] text-[var(--acento)] bg-[var(--acento-claro)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 transition-colors min-h-[44px] ${
              ocupado ? 'opacity-60 cursor-not-allowed' : 'hover:bg-[var(--acento-claro)] hover:border-[var(--acento)]'
            }`}
          >
            {traduciendoEste ? (
              <Ic.Loader size={14} className="animate-spin motion-reduce:animate-none" />
            ) : (
              <Ic.Sparkles size={14} />
            )}
            {traduciendoEste
              ? t('panelCategorias.traduciendo')
              : t('panelCategorias.traducirA', { idioma: t(`idioma.${destino}`) })}
          </button>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor={`${idioma}-cat-nombre`} className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelCategorias.nombre')}
            </label>
            <input
              id={`${idioma}-cat-nombre`}
              className={CAMPO}
              value={trad.nombre}
              onChange={e => onNombre(e.target.value)}
              required
            />
          </div>
          <div>
            <label htmlFor={`${idioma}-cat-slug`} className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelCategorias.slug')}
            </label>
            <input
              id={`${idioma}-cat-slug`}
              className={CAMPO}
              value={trad.slug}
              onChange={e => onSlug(e.target.value)}
              required
              aria-describedby={`${idioma}-cat-slug-ayuda`}
            />
            <p id={`${idioma}-cat-slug-ayuda`} className="text-xs text-slate-500 mt-1">
              {t('panelCategorias.slugAutoAyuda')}
            </p>
          </div>
        </div>
      </div>
    </fieldset>
  )
}
