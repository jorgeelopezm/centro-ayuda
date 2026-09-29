import type { Categoria } from '@/types'

export const categorias: Categoria[] = [
  { id: 'cuenta', slug: 'conta', nombre: 'Conta', icono: 'usuario' },
  { id: 'pagos', slug: 'pagamentos', nombre: 'Pagamentos', icono: 'tarjeta' },
  { id: 'envios', slug: 'envios', nombre: 'Envios', icono: 'paquete' },
  { id: 'devoluciones', slug: 'devolucoes', nombre: 'Devoluções', icono: 'devolver' },
  { id: 'seguridad', slug: 'seguranca', nombre: 'Segurança', icono: 'escudo' },
  { id: 'facturacion', slug: 'faturamento', nombre: 'Faturamento', icono: 'documento' },
]
