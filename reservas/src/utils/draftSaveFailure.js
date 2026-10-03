// Quando o salvamento do rascunho falha, a pessoa precisa saber por quê. O 409
// (EventNotEditable) acontece quando outra aba já enviou o mesmo evento para
// aprovação: nada é sobrescrito e a saída é Meus Eventos ou um evento novo.
export const DRAFT_CONFLICT_MESSAGE =
  "Este evento já foi enviado para aprovação em outra aba. Veja em Meus Eventos ou comece um novo evento.";
export const DRAFT_ERROR_MESSAGE =
  "Não foi possível salvar o rascunho. Verifique a conexão e tente novamente.";

export function isDraftConflict(error) {
  return error?.response?.status === 409;
}

export function draftSaveFailure(error) {
  return isDraftConflict(error)
    ? { kind: "conflict", message: DRAFT_CONFLICT_MESSAGE }
    : { kind: "error", message: DRAFT_ERROR_MESSAGE };
}
