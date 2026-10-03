// Dois separadores do mesmo navegador compartilham o rascunho em andamento pelo
// localStorage. Sem coordenação, ambos enviam POST /events antes de existir um
// eventId e criam dois rascunhos. O lock exclusivo (Web Locks API) serializa a
// criação entre separadores da mesma origem.
export const DRAFT_CREATE_LOCK = "reservas-draft-create";

const EVENT_ID = /^[0-9a-f]{24}$/i;

export function isEventId(value) {
  return typeof value === "string" && EVENT_ID.test(value);
}

// send(id) envia o rascunho: id vazio cria (POST), id válido atualiza (PUT) e
// devolve o eventId. Sem eventId no estado, a criação roda dentro do lock; lá
// dentro relê o localStorage e, se outro separador já criou, atualiza esse.
// O id novo é gravado antes de soltar o lock. Sem navigator.locks, mantém o
// comportamento anterior (somente o single flight do botão).
export async function saveDraftCoordinated({ eventId, storage, locks, send }) {
  if (eventId) {
    const id = await send(eventId);
    storage.setItem("eventId", id);
    return id;
  }
  if (!locks || typeof locks.request !== "function") {
    const id = await send("");
    storage.setItem("eventId", id);
    return id;
  }
  return locks.request(DRAFT_CREATE_LOCK, async () => {
    const stored = storage.getItem("eventId");
    const id = await send(isEventId(stored) ? stored : "");
    storage.setItem("eventId", id);
    return id;
  });
}
