import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { endSession, hasSession, sessionEndedByStorageEvent } from "../src/utils/session.js";

function createStorage(values = {}) {
  return {
    values: { ...values },
    getItem(key) { return this.values[key] ?? null; },
    setItem(key, value) { this.values[key] = value; },
    clear() { this.values = {}; },
  };
}

test("#17 a session needs both the token and the e-mail", () => {
  assert.equal(hasSession(createStorage()), false);
  assert.equal(hasSession(createStorage({ token: "t" })), false);
  assert.equal(hasSession(createStorage({ userEmail: "a@udf.edu.br" })), false);
  assert.equal(hasSession(createStorage({ token: "t", userEmail: "a@udf.edu.br" })), true);
  assert.equal(hasSession(undefined), false);
});

test("#17 leaving removes the session and the saved form drafts", () => {
  const storage = createStorage({ token: "t", userEmail: "a@udf.edu.br", formData: "{}", eventId: "e1" });
  endSession(storage);
  assert.deepEqual(storage.values, {});
  assert.equal(hasSession(storage), false);
});

test("#17 the navbar shows 'Sair' only with a session and follows it", () => {
  const navbar = readFileSync(new URL("../src/components/Navbar/Navbar.jsx", import.meta.url), "utf8");
  assert.match(navbar, /\{loggedIn && \(\s*<button[^>]*id="logout"[^>]*onClick=\{logout\}/);
  assert.match(navbar, /useSyncExternalStore\(\s*subscribeSession/);
});

test("#17 the session is cleared after the navigation to the login page, not before it", () => {
  // Clearing first made the page being left redirect to "acesso negado".
  const navbar = readFileSync(new URL("../src/components/Navbar/Navbar.jsx", import.meta.url), "utf8");
  const logout = navbar.match(/const logout = [^\n]*/)[0];
  assert.match(logout, /go\('\/organizer', \{ loggedOut: true \}\)/);
  assert.doesNotMatch(logout, /endSession/);
  assert.match(navbar, /useEffect\(\(\) => \{\s*if \(location\.state\?\.loggedOut\) endSession\(globalThis\.localStorage\);/);
});

test("#17 ending the session announces it to this tab", () => {
  const events = [];
  globalThis.window = { dispatchEvent: (e) => events.push(e.type), addEventListener() {}, removeEventListener() {} };
  try {
    endSession(createStorage({ token: "t" }));
  } finally {
    delete globalThis.window;
  }
  assert.deepEqual(events, ["labtech:session"]);
});

test("#44 another tab ending the session is detected from the storage event", () => {
  const empty = createStorage();
  const alive = createStorage({ token: "t", userEmail: "a@udf.edu.br" });
  // localStorage.clear() in the other tab: key is null
  assert.equal(sessionEndedByStorageEvent({ key: null }, empty), true);
  // token or e-mail removed
  assert.equal(sessionEndedByStorageEvent({ key: "token", newValue: null }, createStorage({ userEmail: "a@udf.edu.br" })), true);
  assert.equal(sessionEndedByStorageEvent({ key: "userEmail", newValue: null }, createStorage({ token: "t" })), true);
  // unrelated keys, a still valid session, same-tab announcements and no event do not close the tab
  assert.equal(sessionEndedByStorageEvent({ key: "formData", newValue: null }, empty), false);
  assert.equal(sessionEndedByStorageEvent({ key: null }, alive), false);
  assert.equal(sessionEndedByStorageEvent({ key: "token", newValue: "novo" }, alive), false);
  assert.equal(sessionEndedByStorageEvent({ type: "labtech:session" }, empty), false);
  assert.equal(sessionEndedByStorageEvent(undefined, empty), false);
});

test("#44 every private route listens through PrivateRoute and leaves for /organizer", () => {
  // Wiring check only (no browser): the listener lives in the guard all private routes share.
  const guard = readFileSync(new URL("../src/PrivateRoute.jsx", import.meta.url), "utf8");
  assert.match(guard, /addEventListener\("storage", onStorage\)/);
  assert.match(guard, /removeEventListener\("storage", onStorage\)/);
  assert.match(guard, /sessionEndedByStorageEvent\(event, globalThis\.localStorage\)/);
  assert.match(guard, /setIsAuthorized\(false\);\s*navigate\("\/organizer"/);
  for (const route of ["event-type-selection", "event-schedule", "event-confirm-data", "event-confirmation", "my-events"]) {
    const source = readFileSync(new URL(`../app/routes/${route}.jsx`, import.meta.url), "utf8");
    assert.match(source, /<PrivateRoute /, `${route} must use PrivateRoute`);
  }
});
