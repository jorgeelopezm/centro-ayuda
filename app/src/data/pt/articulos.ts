import type { Articulo } from '@/types'

export const articulos: Articulo[] = [
  {
    id: 'direccion-envio',
    slug: 'atualizar-endereco-de-entrega',
    titulo: 'Como atualizar seu endereço de entrega',
    categoria: 'envios',
    actualizado: '2026-07-15',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'Manter seu endereço de entrega atualizado é essencial para garantir que os pedidos cheguem ao lugar certo. Na [EMPRESA] você pode alterá-lo a qualquer momento pelo painel da sua conta, desde que o pedido ainda não tenha saído do centro de distribuição.',
      'Se o pedido já estiver em trânsito, será preciso falar com nossa equipe de suporte antes das 12h do dia seguinte ao envio. Passado esse prazo, o redirecionamento depende da transportadora e não podemos garanti-lo.',
    ],
    howTo: {
      titulo: 'Como alterar seu endereço de entrega',
      pasos: [
        { titulo: 'Acesse sua conta', descripcion: 'Entre na [EMPRESA] com seu e-mail e senha. Se não lembrar da senha, use o link "Esqueceu sua senha?" na página de acesso.' },
        { titulo: 'Vá em Configurações → Endereços', descripcion: 'No menu superior direito, clique no seu avatar e escolha "Minha conta". Depois abra a aba "Endereços salvos".' },
        { titulo: 'Edite ou adicione um endereço', descripcion: 'Clique em "Editar" ao lado do endereço que quer alterar, ou em "Adicionar novo endereço" para cadastrar outro.' },
        { titulo: 'Salve as alterações', descripcion: 'Preencha os campos obrigatórios e clique em "Salvar endereço". O sistema o aplicará automaticamente aos seus próximos pedidos.' },
      ],
    },
    nota: 'As alterações de endereço valem apenas para pedidos futuros. Se você já fez um pedido e precisa mudar o endereço, fale com o suporte o quanto antes.',
    faq: [
      {
        pregunta: 'Posso ter vários endereços de entrega salvos?',
        respuesta: 'Sim. Você pode salvar até 5 endereços diferentes na sua conta. Durante a compra poderá escolher qual usar em cada pedido. O endereço marcado como "padrão" é selecionado automaticamente, mas dá para trocá-lo em qualquer etapa do pagamento.',
      },
      {
        pregunta: 'E se eu informar um endereço errado e o pedido já tiver saído?',
        respuesta: 'Se o pedido já estiver em trânsito, fale imediatamente com nossa equipe de suporte pelo chat ou por e-mail. Vamos tentar combinar o redirecionamento com a transportadora, embora nem sempre seja possível quando o pacote já saiu para entrega. Nesse caso, o pacote pode voltar ao remetente e ser reenviado sem custo adicional.',
      },
    ],
    relacionados: ['seguimiento-pedido', 'plazos-devolucion', 'metodos-pago'],
  },

  {
    id: 'seguimiento-pedido',
    slug: 'rastreamento-de-pedido-em-tempo-real',
    titulo: 'Rastreamento de pedido em tempo real',
    categoria: 'envios',
    actualizado: '2026-07-18',
    minutosLectura: 2,
    destacado: true,
    parrafos: [
      'Todo pedido da [EMPRESA] gera um código de rastreamento assim que sai do centro de distribuição. Com esse código você acompanha em que ponto da entrega o pacote está, sem precisar escrever para o suporte.',
      'O status é atualizado sempre que a transportadora registra a leitura do pacote, normalmente de duas a quatro vezes por dia. Se o status não mudar em 48 horas úteis, vale abrir uma ocorrência.',
    ],
    howTo: {
      titulo: 'Como acompanhar seu pedido',
      pasos: [
        { titulo: 'Abra "Meus pedidos"', descripcion: 'Entre na sua conta e vá até a seção "Meus pedidos", onde aparecem todas as compras em ordem de data.' },
        { titulo: 'Selecione o pedido', descripcion: 'Clique no pedido que quer consultar. Você verá o status atual e o histórico completo de movimentações.' },
        { titulo: 'Consulte o detalhe da entrega', descripcion: 'Clique em "Ver rastreamento" para abrir o detalhe da transportadora, com a data prevista de entrega.' },
      ],
    },
    nota: 'O código de rastreamento pode levar até 24 horas para ficar ativo depois que você recebe o e-mail de confirmação de envio.',
    faq: [
      {
        pregunta: 'Meu pedido está há dias no mesmo status, é normal?',
        respuesta: 'Durante o transporte entre centros logísticos é comum que o status não mude por 24 ou 48 horas. Se passarem mais de dois dias úteis sem nenhuma movimentação, abra uma ocorrência pelo detalhe do pedido e investigaremos com a transportadora.',
      },
      {
        pregunta: 'Posso mudar o endereço com o pedido já enviado?',
        respuesta: 'Depois de enviado, o endereço só pode ser alterado através da transportadora e nem sempre é possível. Fale com o suporte o quanto antes: se o pacote ainda não saiu para entrega, podemos tentar combinar a mudança.',
      },
    ],
    relacionados: ['direccion-envio', 'plazos-devolucion', 'paquete-danado'],
  },

  {
    id: 'plazos-devolucion',
    slug: 'prazos-de-devolucao',
    titulo: 'Prazos de devolução: tudo o que você precisa saber',
    categoria: 'devoluciones',
    actualizado: '2026-07-20',
    minutosLectura: 3,
    destacado: true,
    parrafos: [
      'Você tem 30 dias corridos a partir do recebimento do pedido para solicitar uma devolução. O prazo começa a contar no dia em que o pacote é entregue, não no dia da compra.',
      'Para que a devolução seja aceita, o produto deve estar no estado original, sem uso e com a embalagem intacta. Itens personalizados e produtos digitais têm condições específicas.',
    ],
    howTo: {
      titulo: 'Como calcular seu prazo',
      pasos: [
        { titulo: 'Localize a data de entrega', descripcion: 'Em "Meus pedidos" você verá a data exata em que a transportadora registrou a entrega.' },
        { titulo: 'Some 30 dias corridos', descripcion: 'Conte 30 dias corridos, incluindo fins de semana e feriados, a partir dessa data de entrega.' },
        { titulo: 'Solicite antes do vencimento', descripcion: 'A solicitação precisa ser registrada dentro do prazo. O envio de volta pode ser concluído nos 14 dias seguintes.' },
      ],
    },
    faq: [
      {
        pregunta: 'Quanto tempo leva o reembolso depois da devolução aprovada?',
        respuesta: 'Depois que recebemos o produto no nosso centro de distribuição, a conferência leva de 2 a 5 dias úteis. Uma vez aprovada, a devolução do valor é feita no mesmo meio de pagamento original e pode levar de 3 a 10 dias adicionais para aparecer, conforme a instituição financeira.',
      },
      {
        pregunta: 'Quem paga o frete da devolução?',
        respuesta: 'Se a devolução for por defeito ou por erro nosso, o frete de volta é gratuito e enviamos uma etiqueta pré-paga. Se for desistência da compra, o custo do frete de volta fica por sua conta e é descontado do reembolso.',
      },
    ],
    relacionados: ['iniciar-devolucion', 'paquete-danado', 'metodos-pago'],
  },

  {
    id: 'iniciar-devolucion',
    slug: 'como-iniciar-uma-devolucao',
    titulo: 'Como iniciar uma devolução passo a passo',
    categoria: 'devoluciones',
    actualizado: '2026-07-22',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'Todas as devoluções são feitas pela sua conta, sem precisar ligar nem escrever para o suporte. O sistema gera a etiqueta de envio e indica o ponto de entrega mais próximo.',
      'Antes de começar, confirme que o pedido está dentro do prazo de 30 dias e que você guardou a embalagem original. Sem a embalagem, a devolução pode ser aceita com redução do valor.',
    ],
    howTo: {
      titulo: 'Como solicitar a devolução',
      pasos: [
        { titulo: 'Entre em "Meus pedidos"', descripcion: 'Localize o pedido que contém o item que quer devolver e abra-o.' },
        { titulo: 'Clique em "Solicitar devolução"', descripcion: 'Selecione os itens específicos e o motivo da devolução. O motivo determina quem assume o custo do frete.' },
        { titulo: 'Imprima a etiqueta', descripcion: 'Baixe a etiqueta pré-paga em PDF e cole no pacote, cobrindo qualquer etiqueta anterior.' },
        { titulo: 'Entregue o pacote', descripcion: 'Leve-o ao ponto de coleta indicado ou solicite a coleta em domicílio pela mesma tela.' },
      ],
    },
    nota: 'Guarde o comprovante de postagem até receber a confirmação do reembolso: é sua prova de que o pacote saiu.',
    faq: [
      {
        pregunta: 'Posso devolver apenas uma parte do pedido?',
        respuesta: 'Sim. Ao solicitar a devolução você pode selecionar itens específicos do pedido. Os demais itens não são afetados e o reembolso é calculado só sobre o que foi devolvido, incluindo a parte proporcional do frete quando for o caso.',
      },
      {
        pregunta: 'O que faço se perdi a embalagem original?',
        respuesta: 'Você pode usar outra embalagem que proteja bem o produto. Lembre-se de que a falta da embalagem original pode reduzir o valor reembolsado se afetar o valor de revenda do item.',
      },
    ],
    relacionados: ['plazos-devolucion', 'paquete-danado', 'seguimiento-pedido'],
  },

  {
    id: 'restablecer-contrasena',
    slug: 'redefinir-minha-senha',
    titulo: 'Como redefinir minha senha passo a passo',
    categoria: 'cuenta',
    actualizado: '2026-07-24',
    minutosLectura: 2,
    destacado: true,
    parrafos: [
      'Se você não lembra sua senha, pode redefini-la pela página de acesso sem falar com o suporte. O processo envia um link temporário para o e-mail vinculado à sua conta.',
      'O link expira em 60 minutos por segurança. Se demorar a chegar, verifique a pasta de spam antes de solicitar de novo.',
    ],
    howTo: {
      titulo: 'Como trocar sua senha',
      pasos: [
        { titulo: 'Clique em "Esqueceu sua senha?"', descripcion: 'O link fica abaixo do formulário de acesso, na página de login.' },
        { titulo: 'Informe seu e-mail', descripcion: 'Digite o endereço com que você se cadastrou. Por segurança, a mensagem de confirmação é a mesma exista ou não a conta.' },
        { titulo: 'Abra o link do e-mail', descripcion: 'Você receberá uma mensagem com um link válido por 60 minutos. Abra-o no mesmo navegador, se possível.' },
        { titulo: 'Escolha uma senha nova', descripcion: 'Deve ter pelo menos 10 caracteres e combinar letras e números. Não pode ser igual a nenhuma das suas três senhas anteriores.' },
      ],
    },
    faq: [
      {
        pregunta: 'Não recebo o e-mail de redefinição, o que faço?',
        respuesta: 'Verifique a pasta de spam e confirme que o endereço informado é o do cadastro. Se ainda assim não chegar após 15 minutos, é possível que a conta esteja vinculada a outro e-mail. Nesse caso, fale com o suporte para verificar sua identidade.',
      },
      {
        pregunta: 'Trocar a senha encerra a sessão nos outros dispositivos?',
        respuesta: 'Sim. Ao definir uma senha nova, todas as sessões abertas em outros dispositivos são encerradas automaticamente. Você precisará entrar de novo em cada um deles, o que protege sua conta caso alguém tivesse acesso.',
      },
    ],
    relacionados: ['verificacion-dos-pasos', 'cerrar-cuenta', 'metodos-pago'],
  },

  {
    id: 'cerrar-cuenta',
    slug: 'encerrar-minha-conta',
    titulo: 'Como encerrar sua conta e o que acontece com seus dados',
    categoria: 'cuenta',
    actualizado: '2026-07-10',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'Você pode pedir o encerramento da sua conta a qualquer momento pelas configurações. O encerramento é reversível durante 30 dias; passado esse prazo, a exclusão é definitiva.',
      'Alguns dados precisam ser mantidos por obrigação legal, como as notas fiscais emitidas, que são guardadas pelo período exigido pela legislação fiscal mesmo que a conta não exista mais.',
    ],
    howTo: {
      titulo: 'Como solicitar o encerramento',
      pasos: [
        { titulo: 'Resolva os pedidos em aberto', descripcion: 'Não é possível encerrar a conta com pedidos em trânsito ou devoluções em andamento. Aguarde a conclusão.' },
        { titulo: 'Vá em Configurações → Privacidade', descripcion: 'Dentro de "Minha conta", abra a aba "Privacidade e dados".' },
        { titulo: 'Solicite o encerramento', descripcion: 'Clique em "Encerrar minha conta" e confirme com sua senha. Você receberá um e-mail de confirmação.' },
      ],
    },
    nota: 'Antes de encerrar a conta você pode baixar uma cópia dos seus dados pela mesma tela de privacidade.',
    faq: [
      {
        pregunta: 'Posso recuperar a conta depois de encerrá-la?',
        respuesta: 'Sim, durante os 30 dias seguintes à solicitação. Basta entrar com suas credenciais habituais e confirmar que deseja cancelar o encerramento. Passado esse prazo, os dados são excluídos e não é possível recuperá-los.',
      },
      {
        pregunta: 'Que dados são mantidos após o encerramento?',
        respuesta: 'São mantidos apenas os documentos que a legislação fiscal e contábil obriga a guardar, principalmente as notas fiscais de compra. Esses dados ficam desvinculados do seu perfil e não são usados para nenhuma finalidade comercial.',
      },
    ],
    relacionados: ['restablecer-contrasena', 'verificacion-dos-pasos', 'direccion-facturacion'],
  },

  {
    id: 'metodos-pago',
    slug: 'meios-de-pagamento-aceitos',
    titulo: 'Meios de pagamento aceitos e segurança nas transações',
    categoria: 'pagos',
    actualizado: '2026-07-19',
    minutosLectura: 3,
    destacado: true,
    parrafos: [
      'Aceitamos cartão de crédito e débito, transferência bancária e as principais carteiras digitais. O meio disponível pode variar conforme o país de entrega.',
      'Nenhum dado completo de cartão fica armazenado nos nossos servidores: o pagamento é processado por um gateway certificado que devolve apenas um identificador criptografado.',
    ],
    howTo: {
      titulo: 'Como trocar seu meio de pagamento',
      pasos: [
        { titulo: 'Abra "Meios de pagamento"', descripcion: 'Dentro de "Minha conta", entre na seção "Meios de pagamento salvos".' },
        { titulo: 'Adicione o novo meio', descripcion: 'Clique em "Adicionar meio" e preencha os dados. Será feita uma verificação de R$ 0,00 para confirmar que o cartão é válido.' },
        { titulo: 'Marque como padrão', descripcion: 'Ative a opção "Usar como padrão" para que ele seja selecionado sozinho nas próximas compras.' },
      ],
    },
    faq: [
      {
        pregunta: 'Posso trocar o meio de pagamento de um pedido já confirmado?',
        respuesta: 'Não é possível alterar o meio de pagamento depois de confirmar o pedido, porque a cobrança já foi autorizada. Se precisar usar outro meio, cancele o pedido enquanto estiver no status "Em preparação" e faça-o novamente com o meio correto.',
      },
      {
        pregunta: 'Meu cartão fica salvo nos sistemas de vocês?',
        respuesta: 'Não guardamos o número completo do cartão nem o código de segurança. O gateway de pagamento nos devolve um identificador criptografado que permite repetir cobranças autorizadas, junto com os quatro últimos dígitos para que você o reconheça visualmente.',
      },
    ],
    relacionados: ['direccion-facturacion', 'plazos-devolucion', 'verificacion-dos-pasos'],
  },

  {
    id: 'direccion-facturacion',
    slug: 'atualizar-endereco-de-faturamento',
    titulo: 'Como atualizar meu endereço de faturamento',
    categoria: 'facturacion',
    actualizado: '2026-07-21',
    minutosLectura: 2,
    destacado: true,
    parrafos: [
      'O endereço de faturamento é o que aparece nas suas notas fiscais e deve coincidir com o registrado na sua instituição financeira. É independente do endereço de entrega.',
      'As alterações valem para as notas futuras. Notas já emitidas não podem ser alteradas, mas você pode pedir uma nota de correção se contiverem algum erro.',
    ],
    howTo: {
      titulo: 'Como alterar seus dados de faturamento',
      pasos: [
        { titulo: 'Vá em Configurações → Faturamento', descripcion: 'Dentro de "Minha conta", abra a aba "Dados de faturamento".' },
        { titulo: 'Edite os dados fiscais', descripcion: 'Atualize o nome ou razão social, o documento fiscal e o endereço completo.' },
        { titulo: 'Salve e confira', descripcion: 'Clique em "Salvar". Confira na sua próxima nota fiscal se os dados aparecem corretamente.' },
      ],
    },
    nota: 'Se você fatura como empresa, o documento fiscal precisa estar ativo no registro correspondente ou a nota pode ser rejeitada.',
    faq: [
      {
        pregunta: 'Posso pedir a nota fiscal de um pedido antigo?',
        respuesta: 'Sim. Todas as notas ficam disponíveis na seção "Notas fiscais" da sua conta, com opção de baixar em PDF. Se o pedido for anterior à criação da sua conta, fale com o suporte informando o número do pedido.',
      },
      {
        pregunta: 'Como corrijo uma nota fiscal já emitida?',
        respuesta: 'Notas emitidas não são alteradas: emite-se uma nota de correção que anula a anterior. Solicite-a pelo detalhe da nota indicando qual dado está incorreto, e você a receberá em até 3 dias úteis.',
      },
    ],
    relacionados: ['metodos-pago', 'cerrar-cuenta', 'plazos-devolucion'],
  },

  {
    id: 'verificacion-dos-pasos',
    slug: 'verificacao-em-duas-etapas',
    titulo: 'Ativar a verificação em duas etapas',
    categoria: 'seguridad',
    actualizado: '2026-07-23',
    minutosLectura: 3,
    destacado: false,
    parrafos: [
      'A verificação em duas etapas acrescenta uma segunda checagem ao entrar, de modo que saber sua senha não basta para acessar a conta.',
      'Você pode usar um aplicativo autenticador ou receber o código por mensagem. O aplicativo é a opção recomendada porque funciona sem sinal e é mais difícil de interceptar.',
    ],
    howTo: {
      titulo: 'Como ativar a verificação em duas etapas',
      pasos: [
        { titulo: 'Vá em Configurações → Segurança', descripcion: 'Dentro de "Minha conta", abra a aba "Segurança e acesso".' },
        { titulo: 'Escolha o método', descripcion: 'Selecione "Aplicativo autenticador" ou "Mensagem de texto" e siga as instruções na tela.' },
        { titulo: 'Escaneie o código', descripcion: 'Se escolher o aplicativo, escaneie o código que aparece na tela e digite os seis dígitos que ele mostrar.' },
        { titulo: 'Guarde os códigos de recuperação', descripcion: 'Baixe os códigos de uso único e guarde-os em local seguro: são sua forma de entrar se perder o dispositivo.' },
      ],
    },
    nota: 'Sem os códigos de recuperação, perder o dispositivo implica um processo manual de verificação de identidade que pode levar vários dias.',
    faq: [
      {
        pregunta: 'Perdi o celular com o aplicativo autenticador, como entro?',
        respuesta: 'Use um dos códigos de recuperação que você baixou ao ativar a verificação. Cada código serve uma única vez. Se também não os tiver, fale com o suporte: vamos pedir documentação para verificar sua identidade antes de desativar a proteção.',
      },
      {
        pregunta: 'Posso desativar a verificação em duas etapas?',
        respuesta: 'Sim, pela mesma tela de segurança, confirmando com sua senha e um código válido. Não recomendamos: a verificação em duas etapas é a medida individual que mais reduz o risco de acesso não autorizado à sua conta.',
      },
    ],
    relacionados: ['restablecer-contrasena', 'cerrar-cuenta', 'metodos-pago'],
  },

  {
    id: 'paquete-danado',
    slug: 'meu-pacote-chegou-danificado',
    titulo: 'O que fazer se seu pacote chegar danificado',
    categoria: 'envios',
    actualizado: '2026-07-25',
    minutosLectura: 2,
    destacado: false,
    parrafos: [
      'Se o pacote chegar visivelmente danificado, você pode recusá-lo no momento da entrega ou aceitá-lo registrando a ocorrência no comprovante da transportadora.',
      'Você tem 48 horas a partir da entrega para relatar danos que não sejam visíveis por fora. As fotos da embalagem e do produto são indispensáveis para abrir a reclamação.',
    ],
    howTo: {
      titulo: 'Como relatar um pacote danificado',
      pasos: [
        { titulo: 'Fotografe tudo antes de abrir', descripcion: 'Tire fotos do pacote fechado, da etiqueta e do produto depois de aberto. São a prova da reclamação.' },
        { titulo: 'Abra uma ocorrência', descripcion: 'No detalhe do pedido, clique em "Relatar ocorrência" e escolha "Produto danificado no transporte".' },
        { titulo: 'Anexe as imagens', descripcion: 'Envie as fotos e descreva brevemente o dano. Analisamos as ocorrências em até 2 dias úteis.' },
      ],
    },
    faq: [
      {
        pregunta: 'Preciso devolver o produto danificado?',
        respuesta: 'Depende do item. Em muitos casos autorizamos o reenvio sem necessidade de devolver o original, sobretudo quando o custo da devolução supera o valor do produto. Informaremos isso ao resolver a ocorrência.',
      },
      {
        pregunta: 'Assinei a entrega sem conferir o pacote, perco o direito de reclamar?',
        respuesta: 'Não. Embora assinar sem registrar ocorrência dificulte a reclamação junto à transportadora, você continua tendo 48 horas para relatar danos. As fotos da embalagem são especialmente importantes nesse caso.',
      },
    ],
    relacionados: ['seguimiento-pedido', 'iniciar-devolucion', 'plazos-devolucion'],
  },
]
