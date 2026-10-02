// Client-side session helpers (issue #17).
// The session is the token and e-mail kept in localStorage by the login callback.
export const hasSession = (storage) => Boolean(storage?.getItem("token") && storage?.getItem("userEmail"));

const SESSION_EVENT = "labtech:session";

// Lets components follow the session without reloading: other tabs fire
// "storage", this tab fires SESSION_EVENT.
export function subscribeSession(callback) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  window.addEventListener(SESSION_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(SESSION_EVENT, callback);
  };
}

// Leaving removes the session and the unsent form drafts kept beside it, so the
// next person on the same browser starts clean.
export function endSession(storage) {
  storage?.clear();
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EVENT));
}
