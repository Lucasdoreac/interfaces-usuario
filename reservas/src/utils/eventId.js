const EVENT_ID = /^[0-9a-f]{24}$/i; // ObjectId as text: what the API returns in `eventId`

export const isEventId = (value) => typeof value === "string" && EVENT_ID.test(value);

// An eventId comes from ?eventId= in the URL and goes into a request path, where `..`, `?` and `#`
// would rewrite the path; only a real id may reach it.
export function assertEventId(value) {
  if (!isEventId(value)) {
    const error = new Error("Evento inválido");
    error.status = 400;
    throw error;
  }
  return value;
}

// True when the URL carries an eventId that is not a real id. Pages call this at the entry point so a
// hand-made link is reported and cleared instead of failing later, silently, inside a request.
export function hasInvalidEventIdParam(search) {
  const value = new URLSearchParams(search).get("eventId");
  return value !== null && !isEventId(value);
}
