/**
 * Enum representing the possible statuses for an event
 * @readonly
 * @enum {string}
 */
const EventStatus = Object.freeze({
  DRAFT: "draft",
  WAITING: "waiting",
  APPROVED_BY_COORDENACAO: "approved_by_coordenacao",
  REJECTED_BY_COORDENACAO: "rejected_by_coordenacao",
  APPROVED_BY_REITORIA: "approved_by_reitoria",
  REJECTED_BY_REITORIA: "rejected_by_reitoria",
  REQUESTED_CHANGE: "requested_change",
  DIRECT_APPROVAL: "direct_approval",
});

export default EventStatus;
