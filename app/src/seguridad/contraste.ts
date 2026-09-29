/**
 * Contraste WCAG 2.2 y derivación de la escala de acento. Espejo puro de
 * `api/app/contraste.py`: mismas fórmulas y mismos pares, para adelantar el aviso
 * en la vista previa del editor de marca. **La autoridad es el servidor**: este
 * módulo nunca decide si se guarda; solo previsualiza.
 */

// Umbrales WCAG 2.2 nivel AA.
export const AA_NORMAL = 4.5 // texto normal
export const AA_GRANDE = 3.0 // texto grande, componentes de interfaz y foco

// Colores de referencia fijos de la interfaz.
export const BLANCO = '#ffffff' // texto sobre botón/banner y superficie base
export const FONDO = '#ffffff' // fondo contra el que se mide el anillo de foco

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

export interface ResultadoContraste {
  par: string
  ratio: number
  minimo: number
}

export function hexARgb(color: string): [number, number, number] {
  if (!HEX.test(color)) throw new Error(`Color hexadecimal inválido: ${color}`)
  let h = color.slice(1)
  if (h.length === 3)
    h = h
      .split('')
      .map(c => c + c)
      .join('')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function rgbAHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)))
  return '#' + [clamp(r), clamp(g), clamp(b)].map(v => v.toString(16).padStart(2, '0')).join('')
}

function canalLineal(c8: number): number {
  const c = c8 / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

export function luminanciaRelativa(color: string): number {
  const [r, g, b] = hexARgb(color)
  return 0.2126 * canalLineal(r) + 0.7152 * canalLineal(g) + 0.0722 * canalLineal(b)
}

export function ratioContraste(a: string, b: string): number {
  const la = luminanciaRelativa(a)
  const lb = luminanciaRelativa(b)
  const claro = Math.max(la, lb)
  const oscuro = Math.min(la, lb)
  return (claro + 0.05) / (oscuro + 0.05)
}

function rgbAHsl(r: number, g: number, b: number): [number, number, number] {
  const rn = r / 255
  const gn = g / 255
  const bn = b / 255
  const mx = Math.max(rn, gn, bn)
  const mn = Math.min(rn, gn, bn)
  const l = (mx + mn) / 2
  const d = mx - mn
  if (d === 0) return [0, 0, l]
  const s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn)
  let h: number
  if (mx === rn) h = (((gn - bn) / d) % 6 + 6) % 6
  else if (mx === gn) h = (bn - rn) / d + 2
  else h = (rn - gn) / d + 4
  return [h * 60, s, l]
}

function hslARgb(h: number, s: number, l: number): [number, number, number] {
  if (s === 0) {
    const v = Math.round(l * 255)
    return [v, v, v]
  }
  const c = (1 - Math.abs(2 * l - 1)) * s
  const hp = (((h % 360) + 360) % 360) / 60
  const x = c * (1 - Math.abs((hp % 2) - 1))
  let r = 0
  let g = 0
  let b = 0
  if (hp < 1) [r, g, b] = [c, x, 0]
  else if (hp < 2) [r, g, b] = [x, c, 0]
  else if (hp < 3) [r, g, b] = [0, c, x]
  else if (hp < 4) [r, g, b] = [0, x, c]
  else if (hp < 5) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]
  const m = l - c / 2
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)]
}

function ajustarLuminosidad(color: string, deltaL: number, satMax?: number): string {
  const [r, g, b] = hexARgb(color)
  let [h, s, l] = rgbAHsl(r, g, b)
  if (satMax !== undefined) s = Math.min(s, satMax)
  l = Math.max(0, Math.min(1, l + deltaL))
  return rgbAHex(...hslARgb(h, s, l))
}

export interface TokensAcento {
  hover: string
  claro: string
  foco: string
}

/**
 * Deriva la escala de acento a partir del color base, ajustando la luminosidad.
 * Paridad con `derivar_tokens_acento` de `api/app/contraste.py`.
 */
export function derivarTokensAcento(acento: string): TokensAcento {
  const [r, g, b] = hexARgb(acento)
  const l = rgbAHsl(r, g, b)[2]
  return {
    hover: ajustarLuminosidad(acento, -0.12),
    claro: ajustarLuminosidad(acento, 0.95 - l, 0.3),
    foco: ajustarLuminosidad(acento, 0.1),
  }
}

// Escalones de luminosidad de las tres paradas del banner respecto al acento.
// Cero o negativos (igual o más oscuro): al oscurecer sobre blanco solo aumenta el
// contraste, así que —cumpliendo el acento 4.5:1 con blanco— cada parada lo cumple
// por construcción. La parada inicial es el propio acento; el degradado ahonda hacia
// el final. Paridad con `_BANNER_DELTAS` de `api/app/contraste.py`.
const BANNER_DELTAS = [0.0, -0.08, -0.16] as const

export interface DegradadoBanner {
  desde: string
  medio: string
  hasta: string
}

/**
 * Deriva las tres paradas (0/60/100 %) del degradado del banner a partir del acento.
 * Monocromático: conserva el tono y la saturación del acento y baja la luminosidad en
 * escalones hacia la parada final; cada parada queda igual o más oscura que el acento,
 * así que si el acento cumple 4.5:1 con el texto blanco, cada parada lo cumple también.
 * Paridad con `derivar_degradado_banner` de `api/app/contraste.py`.
 */
export function derivarDegradadoBanner(acento: string): DegradadoBanner {
  const [desde, medio, hasta] = BANNER_DELTAS.map(d => ajustarLuminosidad(acento, d))
  return { desde, medio, hasta }
}

/**
 * Valida el conjunto completo de pares de contraste de la paleta propuesta.
 * Devuelve `null` si toda la paleta cumple AA, o el primer par que falla.
 * Paridad con `validar_paleta` de `api/app/contraste.py`.
 */
export function validarPaleta(
  acento: string,
  bannerDesde: string,
  bannerMedio: string,
  bannerHasta: string,
): ResultadoContraste | null {
  const tokens = derivarTokensAcento(acento)
  const comprobaciones: [string, string, string, number][] = [
    ['Texto sobre el botón de acento', BLANCO, acento, AA_NORMAL],
    ['Estado hover del acento', BLANCO, tokens.hover, AA_NORMAL],
    ['Texto de acento sobre fondo tenue', acento, tokens.claro, AA_NORMAL],
    ['Anillo de foco sobre el fondo', tokens.foco, FONDO, AA_GRANDE],
    ['Texto del banner sobre la parada inicial', BLANCO, bannerDesde, AA_NORMAL],
    ['Texto del banner sobre la parada media', BLANCO, bannerMedio, AA_NORMAL],
    ['Texto del banner sobre la parada final', BLANCO, bannerHasta, AA_NORMAL],
  ]
  for (const [par, a, b, minimo] of comprobaciones) {
    const ratio = ratioContraste(a, b)
    if (ratio < minimo) return { par, ratio: Math.round(ratio * 100) / 100, minimo }
  }
  return null
}

// ── Modo noche (plantilla de documentación) ──────────────────────────────────
// Superficies oscuras de la plantilla (`index.css`, bloque `[data-tema]`): la columna
// de contenido (lo que en claro es `bg-white`) y el fondo de hover (`bg-slate-100`).
export const FONDO_NOCHE = '#0f172a'
export const HOVER_NOCHE = '#1e293b'

function mezclar(a: string, b: string, pesoA: number): string {
  const [ra, ga, ba] = hexARgb(a)
  const [rb, gb, bb] = hexARgb(b)
  return rgbAHex(ra * pesoA + rb * (1 - pesoA), ga * pesoA + gb * (1 - pesoA), ba * pesoA + bb * (1 - pesoA))
}

/**
 * Escala de acento para el modo noche. El acento de marca está validado para fondo
 * claro (4.5:1 con blanco), así que sobre fondo oscuro casi siempre queda corto: aquí
 * se **aclara** en escalones hasta que el texto de acento cumple AA contra la superficie
 * más clara sobre la que puede aparecer (el fondo tenue `claro` o el hover). Cumple por
 * construcción: en el límite el color llega a blanco, que supera 4.5:1 con ambas.
 *
 * - `acento`: texto/iconos de acento y fondo de botones; el texto «blanco» de esos
 *   botones pasa a ser `FONDO_NOCHE` en modo noche, y oscuro sobre claro también cumple.
 * - `claro`: fondo tenue (elemento activo), un velo del acento sobre `FONDO_NOCHE`.
 * - `hover`: algo más claro que `acento` (más contraste en ambos usos).
 * - `foco`: el propio `acento`, ≥ 3:1 sobre cualquier superficie oscura.
 */
export function derivarTokensAcentoNoche(acento: string): TokensAcento & { acento: string } {
  const claro = mezclar(acento, FONDO_NOCHE, 0.22)
  const referencia = luminanciaRelativa(claro) > luminanciaRelativa(HOVER_NOCHE) ? claro : HOVER_NOCHE
  let texto = acento
  for (let i = 0; i < 60 && ratioContraste(texto, referencia) < AA_NORMAL; i++) {
    texto = ajustarLuminosidad(texto, 0.02)
  }
  if (ratioContraste(texto, referencia) < AA_NORMAL) texto = BLANCO
  return { acento: texto, hover: ajustarLuminosidad(texto, 0.08), claro, foco: texto }
}
