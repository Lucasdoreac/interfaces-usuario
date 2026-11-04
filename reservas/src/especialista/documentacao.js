// Documentação pública do sistema especialista de recomendação de salas.
// Cada item declara de onde vem (`fonte`) e em que pé está (`estado`); nada aqui
// afirma o que a fonte não diz. Sem e-mails, telefones nem dados de pessoas.
export const ESTADOS = Object.freeze({
  registrado: "Registrado em documento ou e-mail",
  relato: "Relato do Lucas, ainda não conferido em fonte escrita",
  candidata: "Candidata a regra, falta validação humana",
  pendente: "Pendente",
  feito: "Feito",
});

export const SECOES = Object.freeze([
  {
    id: "o-que-e",
    titulo: "O que é e em que pé está",
    itens: [
      { texto: "Protótipo de um sistema especialista que recomenda salas explicando por quê: cada recomendação mostra a regra, o fato usado e a fonte desse fato.", fonte: "Código do projeto (motor de regras)", estado: "feito" },
      { texto: "Hoje roda só com dados sintéticos identificados. Não está ligado ao fluxo de reserva e não grava reservas.", fonte: "Código do projeto", estado: "feito" },
      { texto: "Localização é informação à parte da recomendação: mostra campus, prédio e andar quando confirmados, lista o que falta e nunca monta trajeto.", fonte: "Código do projeto", estado: "feito" },
      { texto: "As regras atuais (capacidade, recursos, campus) são sintéticas e ainda não foram validadas por quem decide na instituição.", fonte: "Código do projeto", estado: "pendente" },
    ],
  },
  {
    id: "pedidos",
    titulo: "O que a Coordenação enviou e pediu",
    itens: [
      { texto: "28/09: enviou a planilha de oferta 2026/2 (Oferta Simples 09.09) para entender o funcionamento, e disse que a primeira conversa de validação seria com ela.", fonte: "E-mail da Coordenação de 28/09", estado: "registrado" },
      { texto: "28/09: encaminhou o procedimento de reserva de salas e laboratórios da Assessoria Acadêmica (resumido na seção seguinte).", fonte: "E-mail encaminhado em 28/09", estado: "registrado" },
      { texto: "10/10: as três perguntas do Lucas (vigência da oferta, dias e horários, salas em branco e IDs repetidos) foram respondidas com “me pergunta no WhatsApp”; não há resposta escrita.", fonte: "E-mail de 10/10", estado: "registrado" },
      { texto: "07/12: relatório final de atividades, individual, no Blackboard.", fonte: "Mensagem da Coordenação de 31/10, colada pelo Lucas", estado: "relato" },
      { texto: "28/11: apresentação final com pitch dos projetos do LabTech e documentação de software: UML e detalhes do desenvolvimento (fundamentos de tecnologia: IDE, linguagem, banco de dados, repositório etc.).", fonte: "Mensagem da Coordenação de 31/10, colada pelo Lucas", estado: "relato" },
      { texto: "O que ela pediu especificamente sobre o sistema especialista ainda não está em documento: precisa ser registrado após a conversa de validação.", fonte: "Lacuna", estado: "pendente" },
    ],
  },
  {
    id: "procedimento",
    titulo: "Regras do procedimento de reserva (candidatas)",
    itens: [
      { texto: "Cada solicitação vale para um período específico; são três turnos: matutino, vespertino e noturno.", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
      { texto: "Até 2 reservas por dia e até 6 por solicitante.", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
      { texto: "Reservas contínuas cabem num só formulário se seguirem o mesmo padrão de uso.", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
      { texto: "Retorno em até 3 dias úteis; a reserva só vale após confirmação formal da Assessoria, sujeita a disponibilidade e prioridade institucional. Enviar o pedido não garante a sala.", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
      { texto: "Casos excepcionais são analisados pela Assessoria: o sistema deve encaminhar, não decidir.", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
    ],
  },
  {
    id: "dados",
    titulo: "Dados que existem e que faltam",
    itens: [
      { texto: "O catálogo guarda, por sala, só o rótulo e o campus. Prédio, andar, capacidade e recursos não existem no catálogo.", fonte: "Contagem agregada de um backup do banco local de 19/10", estado: "registrado" },
      { texto: "A planilha 2026/2 não tem dia da semana nem horário de início e fim; por isso não dá para inferir disponibilidade de aulas.", fonte: "Planilha de oferta e reports/DADOS.md", estado: "registrado" },
      { texto: "Na importação, 285 linhas da planilha não tinham sala; o banco usa marcador neutro e não inventa sala.", fonte: "reports/DADOS.md", estado: "registrado" },
      { texto: "Fonte oficial de prédio, andar, capacidade e recursos: ainda não identificada. O tour 360 público não foi inspecionado nem tem permissão de reuso confirmada.", fonte: "Lacuna", estado: "pendente" },
    ],
  },
  {
    id: "lfa",
    titulo: "Entrega do projeto final de LFA",
    itens: [
      { texto: "O projeto final precisa ser real: o aluno escolhe uma área, apresenta o tema e a professora valida; um sistema especialista infere para apoiar a decisão e a presença humana é necessária.", fonte: "Transcrição do áudio da aula de 03/11 (ruidosa)", estado: "registrado" },
      { texto: "Sistemas de recomendação está entre as áreas listadas no quadro; recomendar salas se encaixa nessa área.", fonte: "Fotos do quadro, relato do Lucas", estado: "relato" },
      { texto: "Base de conhecimento (fatos e regras SE–ENTÃO) separada do motor de inferência, com encadeamento; a atividade anterior usou 3 fatos, 5 regras e encadeamento para trás, mas isso não é comprovado como exigência da final.", fonte: "Registro do caderno da disciplina (slides de 27/10)", estado: "relato" },
      { texto: "Datas: apresentação do tema em 10/11 e projeto em 17/11 pelo Blackboard, segundo o plano de aulas, cujas colunas estão desalinhadas: confirmar com a professora de LFA.", fonte: "Registro do caderno da disciplina", estado: "relato" },
      { texto: "Alternativa em aberto: sistema de apoio a estudos de impacto ambiental (EIA/RIMA). A escolha entre as duas ainda não foi feita nem validada.", fonte: "Relatório de investigação", estado: "pendente" },
    ],
  },
  {
    id: "dois-usos",
    titulo: "Um projeto, duas entregas",
    itens: [
      { texto: "LFA: o sistema especialista é o projeto final do Lucas na disciplina. A professora de LFA pediu o tema na aula de 03/11 e valida o recorte; apresentação do tema em 10/11 e projeto em 17/11, datas a confirmar.", fonte: "Aula de 03/11 (relato do Lucas) e registro do caderno", estado: "relato" },
      { texto: "LabTech: a mesma fatia entra como pitch em 28/11, com UML e fundamentos de tecnologia, e no relatório individual de 07/12.", fonte: "Mensagem da Coordenação de 31/10", estado: "relato" },
      { texto: "Mesma fonte de verdade para as duas: o motor de regras e a documentação deste repositório. LFA enfatiza base de conhecimento, motor de inferência e validação humana; LabTech enfatiza o produto, a arquitetura e as tecnologias.", fonte: "Proposta de trabalho", estado: "candidata" },
      { texto: "Documentação de software (UML): casos de uso, componentes e sequência da recomendação, a partir do código real do motor e do fluxo de reserva. Ainda não feita.", fonte: "Pedido de 28/11", estado: "pendente" },
      { texto: "Fundamentos de tecnologia: React Router em modo SPA, JavaScript, MongoDB, repositório no GitHub e execução em Docker; precisa ser conferido contra o código antes de entrar no pitch.", fonte: "Código do projeto", estado: "pendente" },
    ],
  },
  {
    id: "roteiro",
    titulo: "Roteiro",
    itens: [
      { texto: "Base de trabalho no staging do fork, com o motor de regras e esta documentação.", fonte: "Repositório", estado: "feito" },
      { texto: "Atualizar as dependências e consolidar o trabalho dos PRs anteriores.", fonte: "Plano de consolidação", estado: "pendente" },
      { texto: "Retomar com a DW: depende de recuperar o acesso aos repositórios da organização, que hoje não resolvem para a conta do Lucas.", fonte: "Verificação de 04/11", estado: "pendente" },
      { texto: "Tela de recomendação com explicações, casos de dado ausente e localização confirmada, sobre dados sintéticos.", fonte: "Backlog", estado: "pendente" },
      { texto: "Validar com a Coordenação o recorte, as regras e as datas; só então trocar dados sintéticos por dados institucionais autorizados.", fonte: "Backlog", estado: "pendente" },
    ],
  },
]);
