import type { Categoria } from '@/types'

export const categorias: Categoria[] = [
  { id: 'cuenta', slug: 'cuenta', nombre: 'Cuenta', icono: 'usuario' },
  { id: 'pagos', slug: 'pagos', nombre: 'Pagos', icono: 'tarjeta' },
  { id: 'envios', slug: 'envios', nombre: 'Envíos', icono: 'paquete' },
  { id: 'devoluciones', slug: 'devoluciones', nombre: 'Devoluciones', icono: 'devolver' },
  { id: 'seguridad', slug: 'seguridad', nombre: 'Seguridad', icono: 'escudo' },
  { id: 'facturacion', slug: 'facturacion', nombre: 'Facturación', icono: 'documento' },
]
