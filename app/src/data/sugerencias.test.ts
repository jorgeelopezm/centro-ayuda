import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  descartarSugerencia,
  generarSugerencia,
  listarCandidatos,
  listarSugerencias,
  obtenerSugerencia,
} from './sugerencias'

/**
 * `sugerencias.ts` son envoltorios finos sobre `apiFetch`: no interpretan la
 * `Response` (eso lo hace cada pantalla). Lo único que vale la pena probar sin
 * DOM es la construcción de la URL/método/cuerpo, con `fetch` sustituido por un
 * doble — mismo patrón que `cargarContenido` en `data/index.test.ts`.
 */
describe('sugerencias', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function fetchDoble() {
    const doble = vi.fn(async () => new Response(JSON.stringify({}), { status: 200 }))
    vi.stubGlobal('fetch', doble)
    return doble
  }

  describe('listarCandidatos', () => {
    it('sin fuente pide la colección completa', async () => {
      const doble = fetchDoble()
      await listarCandidatos()
      expect(doble).toHaveBeenCalledWith('/api/admin/sugerencias/candidatos', expect.anything())
    })

    it('con fuente la añade como query param', async () => {
      const doble = fetchDoble()
      await listarCandidatos('chat_escalado')
      expect(doble).toHaveBeenCalledWith(
        '/api/admin/sugerencias/candidatos?fuente=chat_escalado',
        expect.anything(),
      )
    })
  })

  describe('generarSugerencia', () => {
    it('hace POST con fuente y referencia en el cuerpo', async () => {
      const doble = fetchDoble()
      await generarSugerencia('pregunta_sin_resolver', 'ref-123')
      expect(doble).toHaveBeenCalledWith(
        '/api/admin/sugerencias/generar',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ fuente: 'pregunta_sin_resolver', referencia: 'ref-123' }),
        }),
      )
    })
  })

  describe('listarSugerencias', () => {
    it('pide la cola de pendientes', async () => {
      const doble = fetchDoble()
      await listarSugerencias()
      expect(doble).toHaveBeenCalledWith('/api/admin/sugerencias', expect.anything())
    })
  })

  describe('obtenerSugerencia', () => {
    it('pide el detalle por id', async () => {
      const doble = fetchDoble()
      await obtenerSugerencia('abc-123')
      expect(doble).toHaveBeenCalledWith('/api/admin/sugerencias/abc-123', expect.anything())
    })

    it('codifica el id en la ruta', async () => {
      const doble = fetchDoble()
      await obtenerSugerencia('id con espacio')
      expect(doble).toHaveBeenCalledWith(
        `/api/admin/sugerencias/${encodeURIComponent('id con espacio')}`,
        expect.anything(),
      )
    })
  })

  describe('descartarSugerencia', () => {
    it('hace POST contra /descartar', async () => {
      const doble = fetchDoble()
      await descartarSugerencia('abc-123')
      expect(doble).toHaveBeenCalledWith(
        '/api/admin/sugerencias/abc-123/descartar',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })
})
