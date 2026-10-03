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

export const CHANGE_REQUEST_HEADING = "A Coordenação pediu alterações.";

// What My Events shows for an event: the change-request notice (the reason may be
// absent for events from before it was stored) and the edit link with its label.
export function eventCardView(item) {
  const requested = item?.status === EventStatus.REQUESTED_CHANGE;
  const editable = requested || item?.status === EventStatus.DRAFT;
  return {
    changeNotice: requested
      ? { heading: CHANGE_REQUEST_HEADING, message: changeRequestMessage(item) }
      : null,
    editLink: editable
      ? {
          label: requested ? "Corrigir e reenviar" : "Editar Evento",
          to: `/event/type-selection?eventId=${item._id}`,
        }
      : null,
  };
}
