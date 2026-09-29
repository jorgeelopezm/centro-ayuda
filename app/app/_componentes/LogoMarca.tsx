import type { Idioma } from '@/types'
import { traducir } from '@/i18n/traducir'

/**
 * Marca del centro de ayuda. El nombre es el campo [Empresa]: se recibe por
 * `empresa` e interpola `marca.nombre`. Si hay logotipo subido (`logo`), se muestra
 * la imagen servida por `/api/marca/logo` (mismo origen, alt = nombre de marca); si
 * no, cae al recuadro de iniciales. El nombre textual sigue visible en ambos casos,
 * así que el logotipo nunca es el único medio para reconocer la marca. Server Component.
 *
 * `compacto` reduce el recuadro a 32px para la barra de 64px de la plantilla de
 * documentación; sin él se conserva el tamaño de la plantilla predeterminada.
 */
export function LogoMarca({
  idioma,
  empresa,
  logo = false,
  logoVersion = null,
  compacto = false,
}: {
  idioma: Idioma
  empresa?: string
  logo?: boolean
  logoVersion?: string | null
  compacto?: boolean
}) {
  const t = traducir(idioma)
  const nombre = t('marca.nombre', { empresa: empresa || t('marca.reserva') })
  // Cache-buster: al subir un logo nuevo cambia el hash y el navegador vuelve a
  // pedir la imagen, en vez de reutilizar la copia cacheada de la URL anterior.
  const src = logoVersion ? `/api/marca/logo?v=${logoVersion}` : '/api/marca/logo'
  const recuadro = compacto ? 'w-8 h-8 rounded-lg' : 'w-20 h-20 rounded-xl'
  return (
    <div className={`flex items-center ${compacto ? 'gap-2' : 'gap-4'}`}>
      {logo ? (
        // eslint-disable-next-line @next/next/no-img-element -- binario servido por la API, no un asset estático
        <img
          src={src}
          alt={nombre}
          className={`${recuadro} object-contain select-none`}
        />
      ) : (
        <div
          className={`${recuadro} flex items-center justify-center text-white font-bold tracking-wide select-none ${
            compacto ? 'text-xs' : 'text-lg'
          }`}
          style={{ background: 'var(--acento)' }}
          aria-hidden="true"
        >
          {t('marca.iniciales')}
        </div>
      )}
      <div className="leading-tight">
        <span className={`font-bold text-slate-900 ${compacto ? 'text-lg' : 'text-[20px]'}`}>{nombre}</span>
        <span className={`text-slate-600 font-normal ${compacto ? 'ml-1.5 text-sm' : 'ml-2 text-[16px]'}`}>
          {t('marca.sufijo')}
        </span>
      </div>
    </div>
  )
}
