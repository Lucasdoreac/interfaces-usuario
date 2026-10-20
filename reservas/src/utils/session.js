import { clearAuthStorage } from "./authStorage.js";

export const hasSession = (storage) => Boolean(storage?.getItem("token") && storage?.getItem("userEmail"));

export function sessionEndedByStorageEvent(event, storage) {
  if (!event) return false;
  const touchesSession = event.key === null || event.key === "token" || event.key === "userEmail";
  return touchesSession && !hasSession(storage);
}

const SESSION_EVENT = "labtech:session";

export function subscribeSession(callback) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  window.addEventListener(SESSION_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(SESSION_EVENT, callback);
  };
}

export function endSession(storage) {
  clearAuthStorage(storage);
  for (const key of ["email", "formData", "eventId"]) storage?.removeItem(key);
  if (typeof window !== "undefined") window.dispatchEvent(new Event(SESSION_EVENT));
}
