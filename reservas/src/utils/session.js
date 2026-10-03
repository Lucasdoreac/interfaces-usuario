// Client-side session helpers (issue #17).
// The session is the token and e-mail kept in localStorage by the login callback.
export const hasSession = (storage) => Boolean(storage?.getItem("token") && storage?.getItem("userEmail"));

// Decides, from a "storage" event fired by ANOTHER tab, whether the session this tab was
// using is gone: the token or e-mail was removed, or the whole storage was cleared (key null).
// Same-tab announcements carry no key and are ignored; the other tab already navigated away.
export function sessionEndedByStorageEvent(event, storage) {
  if (!event) return false;
  const touchesSession = event.key === null || event.key === "token" || event.key === "userEmail";
  return touchesSession && !hasSession(storage);
}

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
