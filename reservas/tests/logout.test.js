import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { endSession, hasSession } from "../src/utils/session.js";
import { LOGOUT_UNCONFIRMED_MESSAGE, logoutNavigationState, logoutNoticeFrom } from "../src/utils/logoutNotice.js";

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
  const logout = navbar.match(/const logout = async \(\) => \{[\s\S]*?\n    \};/)[0];
  assert.match(logout, /go\('\/organizer', logoutNavigationState\(confirmed\)\)/);
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

// --- server-side logout (the Auth deletes the session) ---------------------------------------

import { ApiService } from "../src/services/client.js";

function logoutApi({ fetchImpl, storage, logoutTimeoutMs = 50 }) {
  return new ApiService({ baseURL: "https://api.example.test", storage, fetchImpl, logoutTimeoutMs });
}

test("logout tells the server with the token in the body, never the URL, and does not touch local state", async () => {
  const storage = createStorage({ token: "T".repeat(43), userEmail: "a@udf.edu.br" });
  const calls = [];
  const api = logoutApi({
    storage,
    fetchImpl: async (url, options) => { calls.push({ url: String(url), options }); return new Response(null, { status: 204 }); },
  });
  assert.equal(await api.logoutSession(), true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.example.test/auth/logout");
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].options.body), { email: "a@udf.edu.br", token: "T".repeat(43) });
  assert.doesNotMatch(calls[0].url, /T{10}/);
  assert.equal(storage.values.token, "T".repeat(43));   // clearing is the caller's job, after the call
});

test("logout never throws and does not retry: a failing, refusing or asleep server just yields false", async () => {
  const storage = () => createStorage({ token: "t", userEmail: "a@udf.edu.br" });
  let calls = 0;
  const offline = logoutApi({ storage: storage(), fetchImpl: async () => { calls += 1; throw new TypeError("offline"); } });
  assert.equal(await offline.logoutSession(), false);
  const asleep = logoutApi({
    storage: storage(),
    fetchImpl: async () => { calls += 1; return new Response(JSON.stringify({ wake_url: "https://auth.example.test/health" }), { status: 503, headers: { "content-type": "application/json" } }); },
  });
  assert.equal(await asleep.logoutSession(), false);
  assert.equal(calls, 2, "no wake call and no second attempt");
});

test("logout gives up after its own short timeout when the server never answers", async () => {
  const api = logoutApi({
    storage: createStorage({ token: "t", userEmail: "a@udf.edu.br" }),
    fetchImpl: (url, options) => new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    }),
  });
  const started = Date.now();
  assert.equal(await api.logoutSession(), false);
  assert.ok(Date.now() - started < 2000);
});

test("logout without a session makes no request", async () => {
  let calls = 0;
  const api = logoutApi({ storage: createStorage(), fetchImpl: async () => { calls += 1; return new Response(null, { status: 204 }); } });
  assert.equal(await api.logoutSession(), false);
  assert.equal(calls, 0);
});

test("the Sair button asks the server before the local session is cleared, and clears even if that fails", () => {
  const navbar = readFileSync(new URL("../src/components/Navbar/Navbar.jsx", import.meta.url), "utf8");
  const logout = navbar.match(/const logout = async \(\) => \{[\s\S]*?\n    \};/)[0];
  assert.ok(logout.indexOf("await apiService.logoutSession()") !== -1);
  assert.ok(logout.indexOf("await apiService.logoutSession()") < logout.indexOf("go('/organizer'"));
  assert.match(logout, /finally \{[\s\S]*go\('\/organizer', logoutNavigationState\(confirmed\)\)/);   // navigation (and so the clearing) runs on failure too
  assert.match(navbar, /if \(leaving\.current\) return;/);                                // a second click does not start a second logout
});

test("the login notice is decided from the server result: confirmed shows nothing, anything else warns", () => {
  assert.deepEqual(logoutNavigationState(true), { loggedOut: true });
  assert.deepEqual(logoutNavigationState(false), { loggedOut: true, logoutUnconfirmed: true });
  assert.deepEqual(logoutNavigationState(undefined), { loggedOut: true, logoutUnconfirmed: true });
  assert.equal(logoutNoticeFrom({ loggedOut: true }), "");
  assert.equal(logoutNoticeFrom(null), "");
  assert.equal(logoutNoticeFrom({ loggedOut: true, logoutUnconfirmed: true }), LOGOUT_UNCONFIRMED_MESSAGE);
  assert.match(LOGOUT_UNCONFIRMED_MESSAGE, /saiu neste navegador/);
  assert.match(LOGOUT_UNCONFIRMED_MESSAGE, /12 horas/);
});

test("the Navbar passes the server result on and the login page shows it in a status region, only from navigation state", () => {
  const navbar = readFileSync(new URL("../src/components/Navbar/Navbar.jsx", import.meta.url), "utf8");
  const logout = navbar.match(/const logout = async \(\) => \{[\s\S]*?\n    \};/)[0];
  assert.match(logout, /confirmed = \(await apiService\.logoutSession\(\)\) === true/);
  assert.equal((logout.match(/logoutSession\(/g) || []).length, 1);   // no automatic repeat
  assert.doesNotMatch(logout, /token/i);                               // the token is never carried
  const organizer = readFileSync(new URL("../src/pages/organizer/Organizer.jsx", import.meta.url), "utf8");
  assert.match(organizer, /logoutNoticeFrom\(location\.state\)/);
  assert.match(organizer, /role="status"[^>]*>\{logoutNotice\}/);
});
