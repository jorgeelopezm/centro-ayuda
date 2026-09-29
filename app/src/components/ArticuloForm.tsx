import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { IDIOMAS, type Categoria, type Idioma } from '@/types'
import {
  guardarArticulo,
  traducirArticulo,
  type ArticuloAdmin,
  type DestinoArticulo,
  type TraduccionAdmin,
} from '@/data/admin'
import {
  aPayload,
  camposObligatoriosFaltantes,
  draftInicial,
  type CampoFaltante,
  type Draft,
  type TradDraft,
} from '@/data/articuloBorrador'
import { derivarId, derivarSlug } from '@/data/slug'
import { minutosDeArticulo } from '@/data/lecturaMinutos'
import { Tabs, type Pestana } from './Tabs'
import { Ic } from './iconos'

type Props = {
  categorias: Categoria[]
  modo: 'crear' | 'editar'
  inicial?: ArticuloAdmin
  preguntaId?: number
  /** Sugerencia de IA que se está aceptando (spec `sugerencia-articulos-ia`): el guardado va a `.../aceptar` en vez de crear un artículo suelto. */
  sugerenciaId?: string
  onCerrar: () => void
  onGuardado: () => void
}

const CAMPO =
  'w-full min-h-[44px] px-3 py-2 rounded-lg border border-slate-500 bg-white text-slate-900 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:border-transparent'
// Campo de solo lectura: mismo tamaño, aspecto atenuado y sin foco de edición.
const CAMPO_RO =
  'w-full min-h-[44px] px-3 py-2 rounded-lg border border-slate-300 bg-slate-100 text-slate-600 text-sm'
const BOTON_SEC =
  'inline-flex items-center gap-1.5 px-3 rounded-lg border border-slate-500 bg-white text-slate-700 text-sm font-medium hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1 min-h-[44px]'

const HOY = () => new Date().toISOString().slice(0, 10)

// Traduce un campo obligatorio que falta al `id` de su control en el DOM, para
// poder enfocarlo. Los pasos/FAQ se editan con `aria-label` (sin `id`): no se
// enfocan, pero el aviso de texto ya los nombra.
function idDeCampo(cf: CampoFaltante): string | null {
  switch (cf.clave) {
    case 'panelGestion.id':
      return 'af-id'
    case 'panelGestion.categoria':
      return 'af-categoria'
    case 'panelGestion.tituloArticulo':
      return cf.idioma ? `${cf.idioma}-titulo` : null
    case 'panelGestion.slug':
      return cf.idioma ? `${cf.idioma}-slug` : null
    case 'panelGestion.howToTitulo':
      return cf.idioma ? `${cf.idioma}-howto` : null
    default:
      return null
  }
}

function tradAdminADraft(t: TraduccionAdmin, slug: string): TradDraft {
  return {
    slug,
    titulo: t.titulo,
    parrafos: t.parrafos.join('\n'),
    nota: t.nota ?? '',
    howToTitulo: t.howTo.titulo,
    pasos: t.howTo.pasos.map(p => ({ ...p })),
    faq: t.faq.map(f => ({ ...f })),
  }
}

export function ArticuloForm({ categorias, modo, inicial, preguntaId, sugerenciaId, onCerrar, onGuardado }: Props) {
  const { t, i18n } = useTranslation()
  // Idioma de la interfaz (segmento de ruta): decide la pestaña activa por defecto.
  const idiomaInterfaz: Idioma = i18n.language === 'pt' ? 'pt' : 'es'
  const [idiomaActivo, setIdiomaActivo] = useState<Idioma>(() => idiomaInterfaz)
  const [draft, setDraft] = useState<Draft>(() => draftInicial(inicial, categorias[0]?.id ?? ''))
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [traduciendo, setTraduciendo] = useState<Idioma | null>(null)
  // Aviso de que una traducción terminó: la rellena de forma silenciosa, así que
  // un lector de pantalla necesita este mensaje para saber que el contenido cambió.
  const [avisoTrad, setAvisoTrad] = useState<string | null>(null)
  // El id y cada slug se autogeneran del título mientras no se editen a mano.
  const [idEditado, setIdEditado] = useState(false)
  const [slugEditado, setSlugEditado] = useState<Record<Idioma, boolean>>({ es: false, pt: false })

  // Campos que el sistema calcula, no la persona: fecha de hoy (la sella el
  // servidor al guardar) y minutos de lectura por conteo de palabras.
  const hoy = HOY()
  const minutos = minutosDeArticulo(draft.es, draft.pt)

  const patchTrad = (idioma: Idioma, patch: Partial<TradDraft>) =>
    setDraft(d => ({ ...d, [idioma]: { ...d[idioma], ...patch } }))

  function alCambiarTitulo(idioma: Idioma, valor: string) {
    setDraft(d => {
      const nd: Draft = { ...d, [idioma]: { ...d[idioma], titulo: valor } }
      // El slug de este idioma sigue al título mientras no se haya tocado a mano.
      if (!slugEditado[idioma]) nd[idioma] = { ...nd[idioma], slug: derivarSlug(valor) }
      // El id (clave estable) se deriva del título en español, solo al crear.
      if (idioma === 'es' && modo === 'crear' && !idEditado) nd.id = derivarId(valor)
      return nd
    })
  }

  function alCambiarSlug(idioma: Idioma, valor: string) {
    setSlugEditado(s => ({ ...s, [idioma]: true }))
    patchTrad(idioma, { slug: valor })
  }

  function alCambiarId(valor: string) {
    setIdEditado(true)
    setDraft(d => ({ ...d, id: valor }))
  }

  async function traducirDesde(origen: Idioma) {
    if (traduciendo !== null) return // ya hay una traducción en curso: no reentrar
    setError(null)
    setAvisoTrad(null)

    // Candado previo: el backend exige que el idioma origen tenga sus campos
    // obligatorios (título, slug, título de pasos, y título de cada paso/pregunta
    // que se rellene). Traducir un origen incompleto devolvía un 422 críptico y
    // gastaba el proveedor de IA. Se avisa nombrando los campos y se enfoca el
    // primero, sin llamar al backend.
    const faltan = camposObligatoriosFaltantes(draft).filter(cf => cf.idioma === origen)
    if (faltan.length > 0) {
      const campos = faltan
        .map(cf => t(cf.clave, cf.n !== undefined ? { n: cf.n } : undefined))
        .join(', ')
      setError(t('panelGestion.faltanCamposTraducir', { idioma: t(`idioma.${origen}`), campos }))
      const primero = faltan.find(cf => idDeCampo(cf) !== null)
      if (primero) {
        const id = idDeCampo(primero)!
        const enfocar = () => document.getElementById(id)?.focus()
        // El botón de traducir vive en la pestaña del origen (activa), pero por
        // robustez se activa esa pestaña antes de enfocar si no lo estuviera.
        if (origen !== idiomaActivo) {
          setIdiomaActivo(origen)
          requestAnimationFrame(enfocar)
        } else {
          enfocar()
        }
      }
      return
    }

    setTraduciendo(origen)
    try {
      const contenido = aPayload(draft)[origen] // TraduccionAdmin del idioma origen
      const resp = await traducirArticulo(origen, contenido)
      if (!resp.ok) {
        setError(
          resp.status === 409
            ? t('panelGestion.traduccionSinProveedor')
            : t('panelGestion.traduccionError'),
        )
        return
      }
      const tr = (await resp.json()) as TraduccionAdmin
      const destino: Idioma = origen === 'es' ? 'pt' : 'es'
      setDraft(d => ({
        ...d,
        // El slug destino se deriva del título traducido salvo que se haya editado.
        [destino]: tradAdminADraft(tr, slugEditado[destino] ? d[destino].slug : derivarSlug(tr.titulo)),
      }))
      // Muestra el resultado recién traducido cambiando a la pestaña del idioma
      // destino; el aviso `aria-live` anuncia además que la traducción terminó.
      setIdiomaActivo(destino)
      // Reubica el foco en el título del idioma destino (diferido un frame, ya
      // visible): al ocultarse el panel origen, el botón de traducir que tenía el
      // foco desaparece y este caería a <body>, perdiendo la posición de teclado.
      requestAnimationFrame(() => document.getElementById(`${destino}-titulo`)?.focus())
      setAvisoTrad(t('panelGestion.traduccionLista', { idioma: t(`idioma.${destino}`) }))
    } catch {
      setError(t('panelGestion.errorRed'))
    } finally {
      setTraduciendo(null)
    }
  }

  // Etiqueta legible de un campo que falta: su nombre traducido, con el número
  // de fila (pasos/FAQ) y el idioma afectado cuando aplica.
  const etiquetaCampo = (cf: CampoFaltante): string => {
    const nombre = t(cf.clave, cf.n !== undefined ? { n: cf.n } : undefined)
    return cf.idioma
      ? t('panelGestion.campoIdioma', { campo: nombre, idioma: t(`idioma.${cf.idioma}`) })
      : nombre
  }

  async function alEnviar(e: FormEvent) {
    e.preventDefault()
    setError(null)

    // Candado: no se envía nada si faltan campos que el backend exige. El aviso
    // nombra cada campo (y su idioma) y el foco salta al primero con control propio.
    const faltan = camposObligatoriosFaltantes(draft)
    if (faltan.length > 0) {
      setError(t('panelGestion.faltanCampos', { campos: faltan.map(etiquetaCampo).join(', ') }))
      // Primer campo faltante con control propio en el DOM.
      const primero = faltan.find(cf => idDeCampo(cf) !== null)
      if (primero) {
        const id = idDeCampo(primero)!
        const enfocar = () => document.getElementById(id)?.focus()
        // Si el campo vive en la pestaña del idioma no activo, primero se activa
        // esa pestaña y se difiere el foco un frame: enfocar un control dentro de
        // un panel `hidden` no funciona, así que hay que esperar a que sea visible.
        if (primero.idioma && primero.idioma !== idiomaActivo) {
          setIdiomaActivo(primero.idioma)
          requestAnimationFrame(enfocar)
        } else {
          enfocar()
        }
      }
      return
    }

    setEnviando(true)
    try {
      const destino: DestinoArticulo =
        sugerenciaId !== undefined
          ? { tipo: 'desdeSugerencia', sugerenciaId }
          : preguntaId !== undefined
            ? { tipo: 'desdePregunta', preguntaId }
            : modo === 'crear'
              ? { tipo: 'crear' }
              : { tipo: 'editar', articuloId: inicial!.id }

      // Los minutos y la fecha los fija el sistema, no el formulario.
      const payload = aPayload({ ...draft, minutosLectura: minutos, actualizado: hoy })
      const resp = await guardarArticulo(payload, destino)
      if (!resp.ok) {
        setError(resp.status === 409 ? t('panelGestion.errorIdDuplicado') : t('panelGestion.errorGuardar'))
        return
      }
      onGuardado()
    } catch {
      setError(t('panelGestion.errorRed'))
    } finally {
      setEnviando(false)
    }
  }

  const titulo =
    sugerenciaId !== undefined
      ? t('panelGestion.crearDesdeSugerencia')
      : preguntaId !== undefined
        ? t('panelGestion.crearDesdePregunta')
        : modo === 'crear'
          ? t('panelGestion.nuevo')
          : t('panelGestion.editar')

  return (
    <section aria-labelledby="form-articulo-h" className="rounded-2xl border border-[var(--acento-claro)] bg-white p-5 sm:p-6 shadow-xl">
      <div className="flex items-start justify-between gap-3 mb-4">
        <h2 id="form-articulo-h" className="text-lg font-bold text-slate-900">
          {titulo}
        </h2>
        <button
          type="button"
          onClick={onCerrar}
          aria-label={t('panelGestion.cerrar')}
          className="shrink-0 inline-flex items-center justify-center w-11 h-11 rounded-lg border border-slate-500 bg-white text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1"
        >
          <Ic.X size={18} />
        </button>
      </div>

      <form onSubmit={alEnviar} noValidate className="space-y-5">
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
            <label htmlFor="af-id" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelGestion.id')}
            </label>
            <input
              id="af-id"
              className={modo === 'editar' ? CAMPO_RO : CAMPO}
              value={draft.id}
              onChange={e => alCambiarId(e.target.value)}
              disabled={modo === 'editar'}
              required
              aria-describedby="af-id-ayuda"
            />
            <p id="af-id-ayuda" className="text-xs text-slate-500 mt-1">
              {modo === 'editar' ? t('panelGestion.idBloqueadoAyuda') : t('panelGestion.idAutoAyuda')}
            </p>
          </div>
          <div>
            <label htmlFor="af-categoria" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelGestion.categoria')}
            </label>
            <select
              id="af-categoria"
              className={CAMPO}
              value={draft.categoria}
              onChange={e => setDraft(d => ({ ...d, categoria: e.target.value }))}
            >
              {categorias.map(c => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="af-fecha" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelGestion.actualizado')}
            </label>
            <input
              id="af-fecha"
              type="date"
              className={CAMPO_RO}
              value={hoy}
              readOnly
              aria-describedby="af-fecha-ayuda"
            />
            <p id="af-fecha-ayuda" className="text-xs text-slate-500 mt-1">
              {t('panelGestion.actualizadoAyuda')}
            </p>
          </div>
          <div>
            <label htmlFor="af-minutos" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelGestion.minutos')}
            </label>
            <input
              id="af-minutos"
              type="number"
              className={CAMPO_RO}
              value={minutos}
              readOnly
              aria-describedby="af-minutos-ayuda"
            />
            <p id="af-minutos-ayuda" className="text-xs text-slate-500 mt-1">
              {t('panelGestion.minutosAyuda')}
            </p>
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="af-relacionados" className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelGestion.relacionados')}
            </label>
            <input
              id="af-relacionados"
              className={CAMPO}
              value={draft.relacionados}
              onChange={e => setDraft(d => ({ ...d, relacionados: e.target.value }))}
              aria-describedby="af-rel-ayuda"
            />
            <p id="af-rel-ayuda" className="text-xs text-slate-500 mt-1">
              {t('panelGestion.relacionadosAyuda')}
            </p>
          </div>
          <div className="sm:col-span-2">
            <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
              <input
                type="checkbox"
                className="w-5 h-5 rounded border-slate-500 text-[var(--acento)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)]"
                checked={draft.destacado}
                onChange={e => setDraft(d => ({ ...d, destacado: e.target.checked }))}
              />
              {t('panelGestion.destacado')}
            </label>
          </div>
        </div>

        <Tabs
          activa={idiomaActivo}
          onCambio={setIdiomaActivo}
          etiquetaLista={t('panelGestion.idiomasTablist')}
          pestanas={IDIOMAS.map(
            (idioma): Pestana<Idioma> => ({
              id: idioma,
              etiqueta: t(`idioma.${idioma}`),
              contenido: (
                <SeccionIdioma
                  idioma={idioma}
                  trad={draft[idioma]}
                  traduciendo={traduciendo}
                  onPatch={patch => patchTrad(idioma, patch)}
                  onTitulo={valor => alCambiarTitulo(idioma, valor)}
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
            {t('panelGestion.guardar')}
          </button>
          <button type="button" onClick={onCerrar} className={BOTON_SEC}>
            <Ic.X size={15} />
            {t('panelGestion.cancelar')}
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
  onPatch,
  onTitulo,
  onSlug,
  onTraducir,
}: {
  idioma: Idioma
  trad: TradDraft
  traduciendo: Idioma | null
  onPatch: (patch: Partial<TradDraft>) => void
  onTitulo: (valor: string) => void
  onSlug: (valor: string) => void
  onTraducir: () => void
}) {
  const { t } = useTranslation()
  const p = (s: string) => `${idioma}-${s}`
  const destino: Idioma = idioma === 'es' ? 'pt' : 'es'
  const traduciendoEste = traduciendo === idioma
  const ocupado = traduciendo !== null

  const setPaso = (i: number, campo: 'titulo' | 'descripcion', valor: string) =>
    onPatch({ pasos: trad.pasos.map((paso, j) => (j === i ? { ...paso, [campo]: valor } : paso)) })
  const setFaq = (i: number, campo: 'pregunta' | 'respuesta', valor: string) =>
    onPatch({ faq: trad.faq.map((f, j) => (j === i ? { ...f, [campo]: valor } : f)) })

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
              ? t('panelGestion.traduciendo')
              : t('panelGestion.traducirA', { idioma: t(`idioma.${destino}`) })}
          </button>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor={p('titulo')} className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelGestion.tituloArticulo')}
            </label>
            <input id={p('titulo')} className={CAMPO} value={trad.titulo} onChange={e => onTitulo(e.target.value)} required />
          </div>
          <div>
            <label htmlFor={p('slug')} className="block text-sm font-medium text-slate-700 mb-1">
              {t('panelGestion.slug')}
            </label>
            <input
              id={p('slug')}
              className={CAMPO}
              value={trad.slug}
              onChange={e => onSlug(e.target.value)}
              required
              aria-describedby={p('slug-ayuda')}
            />
            <p id={p('slug-ayuda')} className="text-xs text-slate-500 mt-1">
              {t('panelGestion.slugAutoAyuda')}
            </p>
          </div>
        </div>
        <div>
          <label htmlFor={p('parrafos')} className="block text-sm font-medium text-slate-700 mb-1">
            {t('panelGestion.parrafos')}
          </label>
          <textarea
            id={p('parrafos')}
            rows={4}
            className={CAMPO}
            value={trad.parrafos}
            onChange={e => onPatch({ parrafos: e.target.value })}
            aria-describedby={p('parrafos-ayuda')}
          />
          <p id={p('parrafos-ayuda')} className="text-xs text-slate-500 mt-1">
            {t('panelGestion.parrafosAyuda')}
          </p>
        </div>
        <div>
          <label htmlFor={p('nota')} className="block text-sm font-medium text-slate-700 mb-1">
            {t('panelGestion.nota')}
          </label>
          <input id={p('nota')} className={CAMPO} value={trad.nota} onChange={e => onPatch({ nota: e.target.value })} />
        </div>
        <div>
          <label htmlFor={p('howto')} className="block text-sm font-medium text-slate-700 mb-1">
            {t('panelGestion.howToTitulo')}
          </label>
          <input id={p('howto')} className={CAMPO} value={trad.howToTitulo} onChange={e => onPatch({ howToTitulo: e.target.value })} required />
        </div>

        <FilasDinamicas
          etiqueta={t('panelGestion.pasos')}
          items={trad.pasos}
          onAgregar={() => onPatch({ pasos: [...trad.pasos, { titulo: '', descripcion: '' }] })}
          onQuitar={i => onPatch({ pasos: trad.pasos.filter((_, j) => j !== i) })}
          textoAgregar={t('panelGestion.agregarPaso')}
          render={(paso, i) => (
            <div className="grid sm:grid-cols-2 gap-2 flex-1">
              <input
                aria-label={t('panelGestion.pasoTitulo', { n: i + 1 })}
                className={CAMPO}
                value={paso.titulo}
                onChange={e => setPaso(i, 'titulo', e.target.value)}
                placeholder={t('panelGestion.pasoTituloMarcador')}
              />
              <input
                aria-label={t('panelGestion.pasoDescripcion', { n: i + 1 })}
                className={CAMPO}
                value={paso.descripcion}
                onChange={e => setPaso(i, 'descripcion', e.target.value)}
                placeholder={t('panelGestion.pasoDescripcionMarcador')}
              />
            </div>
          )}
        />

        <FilasDinamicas
          etiqueta={t('panelGestion.faq')}
          items={trad.faq}
          onAgregar={() => onPatch({ faq: [...trad.faq, { pregunta: '', respuesta: '' }] })}
          onQuitar={i => onPatch({ faq: trad.faq.filter((_, j) => j !== i) })}
          textoAgregar={t('panelGestion.agregarFaq')}
          render={(f, i) => (
            <div className="grid sm:grid-cols-2 gap-2 flex-1">
              <input
                aria-label={t('panelGestion.faqPregunta', { n: i + 1 })}
                className={CAMPO}
                value={f.pregunta}
                onChange={e => setFaq(i, 'pregunta', e.target.value)}
                placeholder={t('panelGestion.faqPreguntaMarcador')}
              />
              <input
                aria-label={t('panelGestion.faqRespuesta', { n: i + 1 })}
                className={CAMPO}
                value={f.respuesta}
                onChange={e => setFaq(i, 'respuesta', e.target.value)}
                placeholder={t('panelGestion.faqRespuestaMarcador')}
              />
            </div>
          )}
        />
      </div>
    </fieldset>
  )
}

function FilasDinamicas<T>({
  etiqueta,
  items,
  onAgregar,
  onQuitar,
  textoAgregar,
  render,
}: {
  etiqueta: string
  items: T[]
  onAgregar: () => void
  onQuitar: (i: number) => void
  textoAgregar: string
  render: (item: T, i: number) => ReactNode
}) {
  const { t } = useTranslation()
  return (
    <div>
      <p className="block text-sm font-medium text-slate-700 mb-2">{etiqueta}</p>
      <ul className="space-y-2 list-none p-0 m-0">
        {items.map((item, i) => (
          <li key={i} className="flex items-start gap-2">
            {render(item, i)}
            <button
              type="button"
              onClick={() => onQuitar(i)}
              aria-label={t('panelGestion.quitarFila', { n: i + 1 })}
              className="shrink-0 inline-flex items-center justify-center w-11 h-11 rounded-lg border border-slate-500 bg-white text-red-700 hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--acento-foco)] focus-visible:ring-offset-1"
            >
              <Ic.Trash size={15} />
            </button>
          </li>
        ))}
      </ul>
      <button type="button" onClick={onAgregar} className={`${BOTON_SEC} mt-2`}>
        <Ic.Plus size={14} />
        {textoAgregar}
      </button>
    </div>
  )
}
