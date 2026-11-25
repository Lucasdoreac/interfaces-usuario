// Resumo legível do formulário de evento para a tela de confirmação.
// Antes a tela despejava JSON.stringify(formData), com chaves internas,
// logo: {} e campos vazios (issue #36).

import { formatBrasiliaDateTime } from "./dateUtils.js";
const EVENT_TYPES = {
  lecture: "Palestra",
  workshop: "Workshop",
  class: "Aula",
  exam: "Prova",
};

const isEmpty = (value) =>
  value === undefined ||
  value === null ||
  value === "" ||
  (Array.isArray(value) && value.length === 0) ||
  (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0);

const asText = (value) => {
  if (Array.isArray(value)) {
    return value
      .map((item) => (item && typeof item === "object" ? item.name || item.id : item))
      .filter((item) => !isEmpty(item))
      .join(", ");
  }
  return typeof value === "object" ? "" : String(value);
};

const yesNo = (flag, description) => {
  if (flag === "sim") return isEmpty(description) ? "Sim" : `Sim — ${description}`;
  if (flag === "nao") return "Não";
  return "";
};

const formatDate = (iso, zone) => zone === "America/Sao_Paulo"
  ? `${formatBrasiliaDateTime(iso)} (horário de Brasília)`
  : "Horário anterior não confirmado — selecione a sala novamente";

export const summarizeEventData = (formData = {}) => {
  const data = formData || {};
  const rows = [
    ["Título", data.tituloEvento],
    ["Tipo de evento", EVENT_TYPES[data.classificacao] || data.classificacao],
    ["Telefone", data.telefone],
    ["Descrição", data.descricaoEvento],
    ["Curso vinculado", data.courseName],
    ["ODS", data.odsName || data.odsId],
    ["Público-alvo", data.publicoAlvo],
    ["Recursos necessários", data.recursosNecessarios],
    ["Número de participantes", data.numeroParticipantes],
    ["Espaço necessário", data.espacos],
    ["Trilha empreendedora", yesNo(data.trilha, data.trilhaDesc)],
    ["Projeto de extensão", yesNo(data.projeto, data.projetoDesc)],
    ["Alunos monitores", data.alunosMonitores],
    ["Data da reserva", isEmpty(data.reservationDate) ? "" : formatDate(data.reservationDate, data.reservationTimeZone)],
  ];

  return rows
    .map(([label, value]) => ({ label, value: isEmpty(value) ? "" : asText(value) }))
    .filter((row) => row.value !== "");
};
