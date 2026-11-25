import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { ApiService } from "../src/services/client.js";
import { resolveCallback, signIn } from "../src/utils/callbackFlow.js";

function createStorage(values = {}) {
  return {
    values: { ...values },
    getItem(key) { return this.values[key] ?? null; },
    setItem(key, value) { this.values[key] = value; },
    clear() { this.values = {}; },
  };
}

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function recordingApi({ validToken = false } = {}) {
  const calls = { validate: 0, exchange: 0 };
  return {
    calls,
    validateToken: async () => { calls.validate += 1; return validToken; },
    exchangeToken: async () => { calls.exchange += 1; return "session-token"; },
  };
}

test("loading the page with a link never spends it (mail scanners open links)", async () => {
  const api = recordingApi();
  const result = await resolveCallback({
    api, storage: createStorage(), email: "a@udf.edu.br", linkToken: "L".repeat(43),
  });
  assert.deepEqual(result, { action: "needs-click" });
  assert.equal(api.calls.exchange, 0);
});

test("a session stored by an earlier visit keeps working on reload", async () => {
  const api = recordingApi({ validToken: true });
  const storage = createStorage({ token: "session", userEmail: "a@udf.edu.br" });
  const result = await resolveCallback({ api, storage, email: "a@udf.edu.br", linkToken: "L".repeat(43) });
  assert.deepEqual(result, { action: "events" });
  assert.equal(api.calls.exchange, 0);
});

test("a stored session of another address is not reused", async () => {
  const api = recordingApi({ validToken: true });
  const storage = createStorage({ token: "session", userEmail: "other@udf.edu.br" });
  const result = await resolveCallback({ api, storage, email: "a@udf.edu.br", linkToken: "L".repeat(43) });
  assert.equal(result.action, "needs-click");
  assert.equal(api.calls.validate, 0);
});

test("without an address the user goes back to the login page", async () => {
  const result = await resolveCallback({ api: recordingApi(), storage: createStorage(), email: "", linkToken: "x" });
  assert.deepEqual(result, { action: "organizer" });
});

test("without a link or a session the page just waits for the e-mail", async () => {
  const result = await resolveCallback({
    api: recordingApi(), storage: createStorage(), email: "a@udf.edu.br", linkToken: null,
  });
  assert.deepEqual(result, { action: "waiting" });
});

test("the click exchanges the link once and stores only the session token", async () => {
  let posts = 0;
  const api = new ApiService({
    baseURL: "https://api.example.test",
    storage: createStorage(),
    fetchImpl: async () => { posts += 1; return json(200, { token: "session-token" }); },
  });
  const storage = createStorage({ stale: "x" });
  const args = { api, storage, email: "a@udf.edu.br", linkToken: "L".repeat(43) };
  const [first, second] = await Promise.all([signIn(args), signIn(args)]);
  assert.deepEqual([first.action, second.action], ["events", "events"]);
  assert.equal(posts, 1, "a double click must not spend the link twice");
  assert.deepEqual(storage.values, { userEmail: "a@udf.edu.br", token: "session-token" });
});

test("a used or invalid link ends in access denied without storing anything", async () => {
  const api = new ApiService({
    baseURL: "https://api.example.test",
    storage: createStorage(),
    fetchImpl: async () => json(403, { message: "Invalid or expired link" }),
  });
  const storage = createStorage();
  const result = await signIn({ api, storage, email: "a@udf.edu.br", linkToken: "used" });
  assert.deepEqual(result, { action: "denied" });
  assert.deepEqual(storage.values, {});
});

test("the callback page spends the link only from the button's handler", () => {
  const source = readFileSync(new URL("../src/pages/auth-callback/AuthCallBack.jsx", import.meta.url), "utf8");
  const effect = source.match(/useEffect\(\(\) => \{[\s\S]*?\}, \[checkSession\]\);/)?.[0] ?? "";
  assert.ok(effect.includes("checkSession()"), "the load effect must only run the session check");
  assert.ok(!/signIn|exchangeToken/.test(effect), "the load effect must not spend the link");
  const check = source.match(/const checkSession = [\s\S]*?\}, \[queryParams, navigate\]\);/)?.[0] ?? "";
  assert.ok(check && !/signIn\(|exchangeToken/.test(check), "checkSession must not spend the link");
  assert.match(source, /onClick=\{enter\}/);
  assert.ok(!source.includes("exchangeToken"), "the component must go through signIn");
});
