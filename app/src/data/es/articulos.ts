import type { Articulo } from '@/types'

export const articulos: Articulo[] = [
  {
    id: 'direccion-envio',
    slug: 'actualizar-direccion-de-envio',
    titulo: 'Cómo actualizar tu dirección de envío',
    categoria: 'envios',
    actualizado: '2026-07-15',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'Mantener tu dirección de envío actualizada es fundamental para garantizar que tus pedidos lleguen al lugar correcto. En [EMPRESA] puedes cambiarla en cualquier momento desde tu panel de cuenta, siempre que el pedido no haya salido aún del almacén.',
      'Si el pedido ya está en tránsito, deberás ponerte en contacto con nuestro equipo de soporte antes de las 12:00 h del día siguiente al envío. Pasado ese plazo, la redirección dependerá de la empresa transportista y no podemos garantizarla.',
    ],
    howTo: {
      titulo: 'Cómo cambiar tu dirección de envío',
      pasos: [
        { titulo: 'Accede a tu cuenta', descripcion: 'Inicia sesión en [EMPRESA] con tu correo y contraseña. Si no recuerdas tu contraseña, usa el enlace "¿Olvidaste tu contraseña?" en la página de acceso.' },
        { titulo: 'Ve a Configuración → Direcciones', descripcion: 'En el menú superior derecho haz clic en tu avatar y selecciona "Mi cuenta". Luego ve a la pestaña "Direcciones guardadas".' },
        { titulo: 'Edita o añade una dirección', descripcion: 'Haz clic en "Editar" junto a la dirección que quieres modificar, o en "Añadir nueva dirección" para registrar una diferente.' },
        { titulo: 'Guarda los cambios', descripcion: 'Completa los campos requeridos y pulsa "Guardar dirección". El sistema la asignará automáticamente a tus próximos pedidos.' },
      ],
    },
    nota: 'Los cambios de dirección solo aplican a pedidos futuros. Si ya has realizado un pedido y necesitas cambiar la dirección, contacta soporte lo antes posible.',
    faq: [
      {
        pregunta: '¿Puedo tener varias direcciones de envío guardadas?',
        respuesta: 'Sí. Puedes guardar hasta 5 direcciones distintas en tu cuenta. Durante el proceso de compra podrás elegir cuál usar para cada pedido. La dirección marcada como "predeterminada" se seleccionará automáticamente, pero puedes cambiarla en cualquier paso del proceso de pago.',
      },
      {
        pregunta: '¿Qué ocurre si introduzco una dirección incorrecta y el pedido ya salió?',
        respuesta: 'Si el pedido ya está en tránsito, contacta inmediatamente con nuestro equipo de soporte a través del chat o por correo. Intentaremos coordinar con la empresa transportista una redirección, aunque no siempre es posible una vez que el paquete está en reparto. En ese caso, el paquete puede devolverse al remitente y reenviarlo sin coste adicional.',
      },
    ],
    relacionados: ['seguimiento-pedido', 'plazos-devolucion', 'metodos-pago'],
  },

  {
    id: 'seguimiento-pedido',
    slug: 'seguimiento-de-pedido-en-tiempo-real',
    titulo: 'Seguimiento de pedido en tiempo real',
    categoria: 'envios',
    actualizado: '2026-07-18',
    minutosLectura: 2,
    destacado: true,
    parrafos: [
      'Cada pedido de [EMPRESA] genera un código de seguimiento en cuanto sale del almacén. Con ese código puedes consultar en qué punto del reparto se encuentra tu paquete, sin necesidad de escribir a soporte.',
      'El estado se actualiza cada vez que la transportista escanea el paquete, normalmente entre dos y cuatro veces al día. Si el estado no cambia en 48 horas laborables, conviene abrir una incidencia.',
    ],
    howTo: {
      titulo: 'Cómo seguir tu pedido',
      pasos: [
        { titulo: 'Abre "Mis pedidos"', descripcion: 'Entra en tu cuenta y ve a la sección "Mis pedidos", donde aparecen todas tus compras ordenadas por fecha.' },
        { titulo: 'Selecciona el pedido', descripcion: 'Haz clic en el pedido que quieras consultar. Verás su estado actual y el historial completo de movimientos.' },
        { titulo: 'Consulta el detalle del reparto', descripcion: 'Pulsa "Ver seguimiento" para abrir el detalle de la transportista, con la fecha estimada de entrega.' },
      ],
    },
    nota: 'El código de seguimiento puede tardar hasta 24 horas en activarse desde que recibes el correo de confirmación de envío.',
    faq: [
      {
        pregunta: 'Mi pedido lleva días en el mismo estado, ¿es normal?',
        respuesta: 'Durante el transporte entre centros logísticos es habitual que el estado no cambie durante 24 o 48 horas. Si pasan más de dos días laborables sin ningún movimiento, abre una incidencia desde el detalle del pedido y la investigaremos con la transportista.',
      },
      {
        pregunta: '¿Puedo cambiar la dirección con el pedido ya enviado?',
        respuesta: 'Una vez enviado, la dirección solo puede modificarse a través de la transportista y no siempre es posible. Contacta con soporte cuanto antes: si el paquete todavía no ha entrado en reparto, podemos intentar coordinar el cambio.',
      },
    ],
    relacionados: ['direccion-envio', 'plazos-devolucion', 'paquete-danado'],
  },

  {
    id: 'plazos-devolucion',
    slug: 'plazos-de-devolucion',
    titulo: 'Plazos de devolución: todo lo que necesitas saber',
    categoria: 'devoluciones',
    actualizado: '2026-07-20',
    minutosLectura: 3,
    destacado: true,
    parrafos: [
      'Dispones de 30 días naturales desde la recepción del pedido para solicitar una devolución. El plazo empieza a contar el día en que el paquete se entrega, no el día de la compra.',
      'Para que la devolución se acepte, el producto debe conservarse en su estado original, sin usar y con el embalaje intacto. Los artículos personalizados y los productos digitales tienen condiciones específicas.',
    ],
    howTo: {
      titulo: 'Cómo calcular tu plazo',
      pasos: [
        { titulo: 'Localiza la fecha de entrega', descripcion: 'En "Mis pedidos" verás la fecha exacta en la que la transportista registró la entrega.' },
        { titulo: 'Suma 30 días naturales', descripcion: 'Cuenta 30 días naturales, incluyendo fines de semana y festivos, desde esa fecha de entrega.' },
        { titulo: 'Solicita antes de que venza', descripcion: 'La solicitud debe registrarse dentro del plazo. El envío de vuelta puede completarse en los 14 días siguientes.' },
      ],
    },
    faq: [
      {
        pregunta: '¿Cuánto tarda el reembolso una vez aprobada la devolución?',
        respuesta: 'Tras recibir el producto en nuestro almacén, la revisión tarda entre 2 y 5 días laborables. Una vez aprobada, el reembolso se emite al mismo método de pago original y puede tardar entre 3 y 10 días adicionales en aparecer, según tu entidad bancaria.',
      },
      {
        pregunta: '¿Quién paga el envío de la devolución?',
        respuesta: 'Si la devolución se debe a un defecto o a un error nuestro, el envío de vuelta es gratuito y te enviaremos una etiqueta prepagada. Si se trata de un cambio de opinión, el coste del envío de vuelta corre por tu cuenta y se descuenta del reembolso.',
      },
    ],
    relacionados: ['iniciar-devolucion', 'paquete-danado', 'metodos-pago'],
  },

  {
    id: 'iniciar-devolucion',
    slug: 'como-iniciar-una-devolucion',
    titulo: 'Cómo iniciar una devolución paso a paso',
    categoria: 'devoluciones',
    actualizado: '2026-07-22',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'Todas las devoluciones se gestionan desde tu cuenta, sin necesidad de llamar ni escribir a soporte. El sistema genera la etiqueta de envío y te indica el punto de entrega más cercano.',
      'Antes de empezar, comprueba que el pedido está dentro del plazo de 30 días y que conservas el embalaje original. Sin embalaje, la devolución puede aceptarse con una reducción del importe.',
    ],
    howTo: {
      titulo: 'Cómo solicitar la devolución',
      pasos: [
        { titulo: 'Entra en "Mis pedidos"', descripcion: 'Localiza el pedido que contiene el artículo que quieres devolver y ábrelo.' },
        { titulo: 'Pulsa "Solicitar devolución"', descripcion: 'Selecciona los artículos concretos y el motivo de la devolución. El motivo determina quién asume el coste del envío.' },
        { titulo: 'Imprime la etiqueta', descripcion: 'Descarga la etiqueta prepagada en PDF y pégala en el paquete, cubriendo cualquier etiqueta anterior.' },
        { titulo: 'Entrega el paquete', descripcion: 'Llévalo al punto de recogida indicado o solicita una recogida a domicilio desde la misma pantalla.' },
      ],
    },
    nota: 'Guarda el justificante de entrega hasta que recibas la confirmación del reembolso: es tu prueba de que el paquete salió.',
    faq: [
      {
        pregunta: '¿Puedo devolver solo una parte del pedido?',
        respuesta: 'Sí. Al solicitar la devolución puedes seleccionar artículos concretos del pedido. El resto de artículos no se ve afectado y el reembolso se calcula solo sobre lo devuelto, incluida la parte proporcional de los gastos de envío cuando corresponde.',
      },
      {
        pregunta: '¿Qué hago si perdí el embalaje original?',
        respuesta: 'Puedes usar otro embalaje que proteja el producto adecuadamente. Ten en cuenta que la ausencia del embalaje original puede suponer una reducción del importe reembolsado si afecta al valor de reventa del artículo.',
      },
    ],
    relacionados: ['plazos-devolucion', 'paquete-danado', 'seguimiento-pedido'],
  },

  {
    id: 'restablecer-contrasena',
    slug: 'restablecer-mi-contrasena',
    titulo: 'Cómo restablecer mi contraseña paso a paso',
    categoria: 'cuenta',
    actualizado: '2026-07-24',
    minutosLectura: 2,
    destacado: true,
    parrafos: [
      'Si no recuerdas tu contraseña, puedes restablecerla desde la página de acceso sin contactar con soporte. El proceso envía un enlace temporal al correo asociado a tu cuenta.',
      'El enlace caduca a los 60 minutos por seguridad. Si tarda en llegar, revisa la carpeta de correo no deseado antes de volver a solicitarlo.',
    ],
    howTo: {
      titulo: 'Cómo cambiar tu contraseña',
      pasos: [
        { titulo: 'Pulsa "¿Olvidaste tu contraseña?"', descripcion: 'El enlace está bajo el formulario de acceso, en la página de inicio de sesión.' },
        { titulo: 'Introduce tu correo', descripcion: 'Escribe la dirección con la que te registraste. Por seguridad, el mensaje de confirmación es el mismo exista o no la cuenta.' },
        { titulo: 'Abre el enlace del correo', descripcion: 'Recibirás un mensaje con un enlace válido durante 60 minutos. Ábrelo en el mismo navegador si es posible.' },
        { titulo: 'Elige una contraseña nueva', descripcion: 'Debe tener al menos 10 caracteres y combinar letras y números. No puede coincidir con ninguna de tus tres contraseñas anteriores.' },
      ],
    },
    faq: [
      {
        pregunta: 'No recibo el correo de restablecimiento, ¿qué hago?',
        respuesta: 'Revisa la carpeta de correo no deseado y comprueba que la dirección introducida es la de registro. Si sigue sin llegar pasados 15 minutos, es posible que la cuenta esté asociada a otro correo. En ese caso, contacta con soporte para verificar tu identidad.',
      },
      {
        pregunta: '¿Cerrar sesión en el resto de dispositivos al cambiar la contraseña?',
        respuesta: 'Sí. Al establecer una contraseña nueva se cierran automáticamente todas las sesiones abiertas en otros dispositivos. Tendrás que volver a iniciar sesión en cada uno de ellos, lo que protege tu cuenta si alguien tenía acceso.',
      },
    ],
    relacionados: ['verificacion-dos-pasos', 'cerrar-cuenta', 'metodos-pago'],
  },

  {
    id: 'cerrar-cuenta',
    slug: 'cerrar-mi-cuenta',
    titulo: 'Cómo cerrar tu cuenta y qué ocurre con tus datos',
    categoria: 'cuenta',
    actualizado: '2026-07-10',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'Puedes solicitar el cierre de tu cuenta en cualquier momento desde la configuración. El cierre es reversible durante 30 días; pasado ese plazo, la eliminación es definitiva.',
      'Algunos datos deben conservarse por obligación legal, como las facturas emitidas, que se guardan durante el periodo que exige la normativa fiscal aunque la cuenta ya no exista.',
    ],
    howTo: {
      titulo: 'Cómo solicitar el cierre',
      pasos: [
        { titulo: 'Resuelve los pedidos abiertos', descripcion: 'No es posible cerrar la cuenta con pedidos en tránsito o devoluciones en curso. Espera a que se completen.' },
        { titulo: 'Ve a Configuración → Privacidad', descripcion: 'Dentro de "Mi cuenta", abre la pestaña "Privacidad y datos".' },
        { titulo: 'Solicita el cierre', descripcion: 'Pulsa "Cerrar mi cuenta" y confirma con tu contraseña. Recibirás un correo de confirmación.' },
      ],
    },
    nota: 'Antes de cerrar la cuenta puedes descargar una copia de tus datos desde la misma pantalla de privacidad.',
    faq: [
      {
        pregunta: '¿Puedo recuperar la cuenta después de cerrarla?',
        respuesta: 'Sí, durante los 30 días siguientes a la solicitud. Basta con iniciar sesión con tus credenciales habituales y confirmar que quieres cancelar el cierre. Pasado ese plazo los datos se eliminan y no es posible recuperarlos.',
      },
      {
        pregunta: '¿Qué datos se conservan tras el cierre?',
        respuesta: 'Se conservan únicamente los documentos que la normativa fiscal y contable obliga a mantener, principalmente las facturas de compra. Estos datos quedan disociados de tu perfil y no se usan con ninguna finalidad comercial.',
      },
    ],
    relacionados: ['restablecer-contrasena', 'verificacion-dos-pasos', 'direccion-facturacion'],
  },

  {
    id: 'metodos-pago',
    slug: 'metodos-de-pago-aceptados',
    titulo: 'Métodos de pago aceptados y seguridad en transacciones',
    categoria: 'pagos',
    actualizado: '2026-07-19',
    minutosLectura: 3,
    destacado: true,
    parrafos: [
      'Aceptamos tarjeta de crédito y débito, transferencia bancaria y los principales monederos digitales. El método disponible puede variar según el país de envío.',
      'Ningún dato completo de tarjeta se almacena en nuestros servidores: el pago se procesa a través de una pasarela certificada que devuelve únicamente un identificador cifrado.',
    ],
    howTo: {
      titulo: 'Cómo cambiar tu método de pago',
      pasos: [
        { titulo: 'Abre "Métodos de pago"', descripcion: 'Dentro de "Mi cuenta", entra en la sección "Métodos de pago guardados".' },
        { titulo: 'Añade el método nuevo', descripcion: 'Pulsa "Añadir método" y completa los datos. Se realizará una verificación de 0 € para comprobar que la tarjeta es válida.' },
        { titulo: 'Márcalo como predeterminado', descripcion: 'Activa la casilla "Usar como predeterminado" para que se seleccione solo en tus próximas compras.' },
      ],
    },
    faq: [
      {
        pregunta: '¿Puedo cambiar el método de pago de un pedido ya confirmado?',
        respuesta: 'No es posible modificar el método de pago una vez confirmado el pedido, porque el cargo ya se ha autorizado. Si necesitas usar otro método, cancela el pedido mientras esté en estado "En preparación" y vuelve a realizarlo con el método correcto.',
      },
      {
        pregunta: '¿Se guarda mi tarjeta en vuestros sistemas?',
        respuesta: 'No guardamos el número completo de la tarjeta ni el código de seguridad. La pasarela de pago nos devuelve un identificador cifrado que permite repetir cobros autorizados, junto a los cuatro últimos dígitos para que puedas identificarla visualmente.',
      },
    ],
    relacionados: ['direccion-facturacion', 'plazos-devolucion', 'verificacion-dos-pasos'],
  },

  {
    id: 'direccion-facturacion',
    slug: 'actualizar-direccion-de-facturacion',
    titulo: 'Cómo actualizar mi dirección de facturación',
    categoria: 'facturacion',
    actualizado: '2026-07-21',
    minutosLectura: 2,
    destacado: true,
    parrafos: [
      'La dirección de facturación es la que aparece en tus facturas y debe coincidir con la registrada en tu entidad bancaria. Es independiente de la dirección de envío.',
      'Los cambios se aplican a las facturas futuras. Las facturas ya emitidas no pueden modificarse, pero puedes solicitar una factura rectificativa si contienen un error.',
    ],
    howTo: {
      titulo: 'Cómo cambiar tus datos de facturación',
      pasos: [
        { titulo: 'Ve a Configuración → Facturación', descripcion: 'Dentro de "Mi cuenta", abre la pestaña "Datos de facturación".' },
        { titulo: 'Edita los datos fiscales', descripcion: 'Actualiza el nombre o razón social, el identificador fiscal y la dirección completa.' },
        { titulo: 'Guarda y verifica', descripcion: 'Pulsa "Guardar". Comprueba en tu próxima factura que los datos aparecen correctamente.' },
      ],
    },
    nota: 'Si facturas como empresa, el identificador fiscal debe estar activo en el registro correspondiente o la factura podría rechazarse.',
    faq: [
      {
        pregunta: '¿Puedo pedir una factura de un pedido antiguo?',
        respuesta: 'Sí. Todas las facturas están disponibles en la sección "Facturas" de tu cuenta, con la posibilidad de descargarlas en PDF. Si el pedido es anterior a la creación de tu cuenta, contacta con soporte indicando el número de pedido.',
      },
      {
        pregunta: '¿Cómo corrijo una factura ya emitida?',
        respuesta: 'Las facturas emitidas no se modifican: se emite una factura rectificativa que anula la anterior. Solicítala desde el detalle de la factura indicando qué dato es incorrecto, y la recibirás en un plazo de 3 días laborables.',
      },
    ],
    relacionados: ['metodos-pago', 'cerrar-cuenta', 'plazos-devolucion'],
  },

  {
    id: 'verificacion-dos-pasos',
    slug: 'verificacion-en-dos-pasos',
    titulo: 'Activar la verificación en dos pasos',
    categoria: 'seguridad',
    actualizado: '2026-07-23',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'La verificación en dos pasos añade una segunda comprobación al iniciar sesión, de modo que conocer tu contraseña no basta para entrar en tu cuenta.',
      'Puedes usar una aplicación de autenticación o recibir el código por mensaje. La aplicación es la opción recomendada porque funciona sin cobertura y es más difícil de interceptar.',
    ],
    howTo: {
      titulo: 'Cómo activar la verificación en dos pasos',
      pasos: [
        { titulo: 'Ve a Configuración → Seguridad', descripcion: 'Dentro de "Mi cuenta", abre la pestaña "Seguridad y acceso".' },
        { titulo: 'Elige el método', descripcion: 'Selecciona "Aplicación de autenticación" o "Mensaje de texto" y sigue las instrucciones en pantalla.' },
        { titulo: 'Escanea el código', descripcion: 'Si eliges la aplicación, escanea el código que aparece en pantalla y escribe los seis dígitos que te muestre.' },
        { titulo: 'Guarda los códigos de recuperación', descripcion: 'Descarga los códigos de un solo uso y guárdalos en un lugar seguro: son tu vía de entrada si pierdes el dispositivo.' },
      ],
    },
    nota: 'Sin los códigos de recuperación, perder el dispositivo implica un proceso manual de verificación de identidad que puede tardar varios días.',
    faq: [
      {
        pregunta: 'He perdido el móvil con la aplicación de autenticación, ¿cómo entro?',
        respuesta: 'Usa uno de los códigos de recuperación que descargaste al activar la verificación. Cada código sirve una sola vez. Si tampoco los conservas, contacta con soporte: te pediremos documentación para verificar tu identidad antes de desactivar la protección.',
      },
      {
        pregunta: '¿Puedo desactivar la verificación en dos pasos?',
        respuesta: 'Sí, desde la misma pantalla de seguridad, confirmando con tu contraseña y un código válido. No lo recomendamos: la verificación en dos pasos es la medida individual que más reduce el riesgo de acceso no autorizado a tu cuenta.',
      },
    ],
    relacionados: ['restablecer-contrasena', 'cerrar-cuenta', 'metodos-pago'],
  },

  {
    id: 'paquete-danado',
    slug: 'mi-paquete-llego-danado',
    titulo: 'Qué hacer si tu paquete llega dañado',
    categoria: 'envios',
    actualizado: '2026-07-25',
    minutosLectura: 2,
    destacado: false,
    parrafos: [
      'Si el paquete llega visiblemente dañado, puedes rechazarlo en el momento de la entrega o aceptarlo indicando la incidencia en el albarán de la transportista.',
      'Dispones de 48 horas desde la entrega para reportar daños no visibles desde fuera. Las fotografías del embalaje y del producto son imprescindibles para tramitar la reclamación.',
    ],
    howTo: {
      titulo: 'Cómo reportar un paquete dañado',
      pasos: [
        { titulo: 'Fotografía todo antes de desembalar', descripcion: 'Haz fotos del paquete cerrado, de la etiqueta y del producto una vez abierto. Son la prueba de la reclamación.' },
        { titulo: 'Abre una incidencia', descripcion: 'Desde el detalle del pedido, pulsa "Reportar incidencia" y selecciona "Producto dañado en el transporte".' },
        { titulo: 'Adjunta las imágenes', descripcion: 'Sube las fotografías y describe brevemente el daño. Revisamos las incidencias en un plazo de 2 días laborables.' },
      ],
    },
    faq: [
      {
        pregunta: '¿Tengo que devolver el producto dañado?',
        respuesta: 'Depende del artículo. En muchos casos autorizamos el reenvío sin necesidad de devolver el original, sobre todo si el coste de la devolución supera el valor del producto. Te lo indicaremos al resolver la incidencia.',
      },
      {
        pregunta: 'Firmé la entrega sin revisar el paquete, ¿pierdo el derecho a reclamar?',
        respuesta: 'No. Aunque firmar sin incidencias complica la reclamación frente a la transportista, sigues teniendo 48 horas para reportar daños. Las fotografías del embalaje son especialmente importantes en este caso.',
      },
    ],
    relacionados: ['seguimiento-pedido', 'iniciar-devolucion', 'plazos-devolucion'],
  },
]
