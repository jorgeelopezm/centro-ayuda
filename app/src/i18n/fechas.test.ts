import { describe, expect, it } from 'vitest'
import { IDIOMAS } from '@/types'
import { FECHA_LARGA, fechaLegible } from './fechas'

describe('fechaLegible', () => {
  it('muestra el mismo día que dice la fecha ISO', () => {
    // El motivo de existir de esta función. `new Date('2026-07-25')` se lee como
    // medianoche UTC: en cualquier huso al oeste de Greenwich la fecha mostrada
    // retrocede al 24. Con `T00:00:00` se lee como medianoche local y el día
    // coincide siempre, corra el test donde corra.
    for (const idioma of IDIOMAS) {
      expect(fechaLegible('2026-07-25', idioma)).toContain('25')
      expect(fechaLegible('2026-07-25', idioma)).not.toContain('24')
    }
  })

  it('no cambia de día en el primero ni en el último del mes', () => {
    // Los bordes son donde el desfase de huso se lleva por delante el mes entero.
    expect(fechaLegible('2026-01-01', 'es', FECHA_LARGA)).toBe('1 de enero de 2026')
    expect(fechaLegible('2026-12-31', 'es', FECHA_LARGA)).toBe('31 de diciembre de 2026')
  })

  it('traduce el mes al idioma pedido', () => {
    expect(fechaLegible('2026-07-25', 'es', FECHA_LARGA)).toBe('25 de julio de 2026')
    expect(fechaLegible('2026-07-25', 'pt', FECHA_LARGA)).toBe('25 de julho de 2026')
  })

  it('sin opciones da el formato corto de cada idioma', () => {
    // Es lo que usa la tabla del panel, donde la columna es estrecha.
    expect(fechaLegible('2026-07-25', 'es')).toBe('25/7/2026')
    expect(fechaLegible('2026-07-25', 'pt')).toBe('25/07/2026')
  })

  it('mantiene el día que se pone en el atributo datetime del <time>', () => {
    // El marcado es <time dateTime={iso}>{fechaLegible(iso)}</time>: si el texto
    // visible y el atributo se refieren a días distintos, la fecha accesible
    // miente respecto a la que se lee.
    for (const iso of ['2026-01-01', '2026-02-28', '2026-07-25', '2026-12-31']) {
      const dia = Number(iso.slice(8, 10))
      const visible = fechaLegible(iso, 'es', FECHA_LARGA)
      expect(Number(visible.split(' ')[0])).toBe(dia)
    }
  })

  it('respeta el año bisiesto', () => {
    expect(fechaLegible('2028-02-29', 'es', FECHA_LARGA)).toBe('29 de febrero de 2028')
  })
})
