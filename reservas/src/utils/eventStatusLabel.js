import EventStatus from "./EventStatus.js";

const LABELS = {
  [EventStatus.DRAFT]: "Rascunho",
  [EventStatus.WAITING]: "Aguardando",
  [EventStatus.APPROVED_BY_COORDENACAO]: "Aprovado pela Coordenação",
  [EventStatus.REJECTED_BY_COORDENACAO]: "Rejeitado pela Coordenação",
  [EventStatus.APPROVED_BY_REITORIA]: "Aprovado pela Reitoria",
  [EventStatus.REJECTED_BY_REITORIA]: "Rejeitado pela Reitoria",
  [EventStatus.REQUESTED_CHANGE]: "Alterações Solicitadas",
  [EventStatus.DIRECT_APPROVAL]: "Aprovado Diretamente",
};

export const statusLabel = (status) => LABELS[status] || status || "Desconhecido";

// The coordinator's reason, only while the event is waiting for the organizer.
export function changeRequestMessage(item) {
  if (item?.status !== EventStatus.REQUESTED_CHANGE) return null;
  const message =
    typeof item.changeRequest?.message === "string"
      ? item.changeRequest.message.trim()
      : "";
  return message || null;
}
