import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { endSession, hasSession } from "../src/utils/session.js";

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
