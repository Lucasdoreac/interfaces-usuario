// Limites, origem e pendências do sistema especialista. Cada item declara de onde
// vem (`fonte`) e em que pé está (`estado`); nada aqui afirma o que a fonte não
// diz. Sem e-mails, telefones nem dados de pessoas.
export const ESTADOS = Object.freeze({
  registrado: "Registrado em documento ou e-mail",
  relato: "Relato do Lucas, ainda não conferido em fonte escrita",
  candidata: "Candidata a regra, falta validação humana",
  pendente: "Pendente",
  feito: "Feito",
});

export const SECOES = Object.freeze([
  {
    id: "limites",
    titulo: "Limites e dados",
    itens: [
      { texto: "A demonstração usa quatro salas sintéticas. O catálogo real guarda, por sala, só o rótulo e o campus: prédio, andar, capacidade e recursos não existem nele.", fonte: "Contagem agregada de um backup do banco local de 19/10", estado: "registrado" },
      { texto: "A planilha de oferta 2026/2 não tem dia da semana nem horário; por isso o sistema não infere disponibilidade de aulas.", fonte: "Planilha de oferta e reports/DADOS.md", estado: "registrado" },
      { texto: "As regras atuais (capacidade, recursos, campus) são sintéticas e ainda não foram validadas por quem decide na instituição.", fonte: "Código do projeto", estado: "pendente" },
      { texto: "Localização mostra só o que está confirmado e nunca monta trajeto; fonte oficial de prédio, andar, capacidade e recursos ainda não identificada.", fonte: "Lacuna", estado: "pendente" },
    ],
  },
  {
    id: "regras-candidatas",
    titulo: "Regras do procedimento de reserva, candidatas",
    itens: [
      { texto: "Cada solicitação vale para um período; são três turnos (matutino, vespertino, noturno).", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
      { texto: "Até 2 reservas por dia e até 6 por solicitante; reservas contínuas cabem num só formulário.", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
      { texto: "A reserva só vale após confirmação formal da Assessoria, sujeita a disponibilidade e prioridade; casos excepcionais vão para a Assessoria, que decide.", fonte: "Procedimento da Assessoria Acadêmica, 28/09", estado: "candidata" },
    ],
  },
  {
    id: "entregas",
    titulo: "Entregas e datas",
    itens: [
      { texto: "28/11: apresentação final com pitch dos projetos do LabTech e documentação de software (UML e fundamentos de tecnologia). Esta página é a base dessa documentação.", fonte: "Mensagem da Coordenação de 31/10, colada pelo Lucas", estado: "relato" },
      { texto: "07/12: relatório final de atividades, individual, no Blackboard.", fonte: "Mensagem da Coordenação de 31/10, colada pelo Lucas", estado: "relato" },
      { texto: "LFA: o sistema é o projeto final da disciplina; o tema é validado pela professora (apresentação em 10/11 e projeto em 17/11, datas a confirmar).", fonte: "Aula de 03/11 e registro do caderno", estado: "relato" },
      { texto: "Validar com a Coordenação o recorte, as regras e as datas antes de trocar dados sintéticos por dados institucionais autorizados.", fonte: "Backlog", estado: "pendente" },
    ],
  },
  {
    id: "proximos",
    titulo: "Próximos passos",
    itens: [
      { texto: "Ligar a recomendação à lista real de salas da API e ao fluxo de pedido de reserva.", fonte: "Backlog", estado: "pendente" },
      { texto: "Encadeamento de fatos derivados no motor (hoje cada regra lê fatos diretos).", fonte: "Backlog", estado: "pendente" },
      { texto: "Atualizar dependências, consolidar os PRs anteriores e retomar com a DW quando o acesso aos repositórios da organização voltar.", fonte: "Plano de consolidação", estado: "pendente" },
    ],
  },
]);
