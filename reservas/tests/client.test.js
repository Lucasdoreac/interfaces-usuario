import assert from "node:assert/strict";
import { test } from "node:test";
import { ApiService } from "../src/services/client.js";

function createStorage(values = {}) {
  return {
    values: { ...values },
    getItem(key) { return this.values[key] ?? null; },
    setItem(key, value) { this.values[key] = value; },
    clear() { this.values = {}; },
  };
}

test("posts auth email with encoded query and preserves the user email", async () => {
  const storage = createStorage({ token: "jwt-123", userEmail: "old@example.com" });
  let request;
  const api = new ApiService({
    baseURL: "https://api.example.test/",
    storage,
    fetchImpl: async (url, options) => {
      request = { url: String(url), options };
      return new Response(JSON.stringify({ sent: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  assert.equal(await api.postAuthMail("lucas.dorea+dev@cs.udf.edu.br"), true);
  assert.equal(request.url, "https://api.example.test/auth/send-link?email=lucas.dorea%2Bdev%40cs.udf.edu.br");
  assert.equal(request.options.headers.get("Authorization"), "Bearer jwt-123");
  assert.equal(request.options.headers.get("email"), "old@example.com");
  assert.equal(storage.getItem("userEmail"), "lucas.dorea+dev@cs.udf.edu.br");
  assert.equal(storage.getItem("token"), null);
});

test("serializes query parameters and returns decoded JSON", async () => {
  let requestUrl;
  const api = new ApiService({
    baseURL: "http://api.example.test",
    storage: createStorage(),
    fetchImpl: async (url) => {
      requestUrl = String(url);
      return new Response(JSON.stringify({ courses: [{ id: "c1" }] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  assert.deepEqual(await api.searchCourses("Computer Science"), { courses: [{ id: "c1" }] });
  assert.equal(requestUrl, "http://api.example.test/courses?course_name=Computer+Science");
});

test("submits an event and its reservation through one API request", async () => {
  const calls = [];
  const event = {
    tituloEvento: "Palestra",
    classificacao: "lecture",
    roomId: "room-42",
    reservationDate: "2031-03-12T10:00:00.000Z",
  };
  const api = new ApiService({
    baseURL: "https://api.example.test",
    storage: createStorage({ token: "jwt-123", userEmail: "owner@udf.edu.br" }),
    fetchImpl: async (url, options) => {
      calls.push({ url: String(url), options });
      return new Response(JSON.stringify({ eventId: "event-123" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  assert.equal(await api.submitEventForApproval("event-123", event), "event-123");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://api.example.test/events/event-123/submit");
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].options.body), event);
  assert.equal(calls[0].options.headers.get("token"), "jwt-123");
  assert.equal(calls[0].options.headers.get("email"), "owner@udf.edu.br");
});

test("returns null for a failed auth request", async () => {
  const api = new ApiService({
    baseURL: "http://api.example.test",
    storage: createStorage(),
    fetchImpl: async () => new Response("unavailable", { status: 502 }),
  });

  assert.equal(await api.postAuthMail("user@udf.edu.br"), null);
});

test("reports auth dry-run without clearing session or treating it as delivery", async () => {
  const storage = createStorage({ token: "existing-token", userEmail: "saved@udf.edu.br" });
  const api = new ApiService({
    baseURL: "http://api.example.test",
    storage,
    fetchImpl: async () => new Response(
      JSON.stringify({ message: "Email dry-run enabled; no email sent" }),
      { status: 202, headers: { "content-type": "application/json" } },
    ),
  });

  assert.deepEqual(await api.postAuthMail("reviewer@cs.udf.edu.br"), { dryRun: true });
  assert.equal(storage.getItem("token"), "existing-token");
  assert.equal(storage.getItem("userEmail"), "saved@udf.edu.br");
});

test("validates auth token with URLSearchParams and authorization headers", async () => {
  const storage = createStorage({ token: "jwt-456", userEmail: "user@udf.edu.br" });
  let request;
  const api = new ApiService({
    baseURL: "http://api.example.test",
    storage,
    fetchImpl: async (url, options) => {
      request = { url: String(url), options };
      return new Response("true", {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });

  assert.equal(await api.validateToken("hash-456", "user@udf.edu.br"), true);
  assert.equal(request.url, "http://api.example.test/auth/validate?token=hash-456&email=user%40udf.edu.br");
  assert.equal(request.options.headers.get("token"), "jwt-456");
  assert.equal(request.options.headers.get("email"), "user@udf.edu.br");
});

test("calls the injected fetch function with the global receiver", async () => {
  let receiver;
  const api = new ApiService({
    baseURL: "http://api.example.test",
    storage: createStorage(),
    fetchImpl: function (url) {
      receiver = this;
      return Promise.resolve(new Response("ok", { status: 200 }));
    },
  });

  await api.request("GET", "/health");
  assert.equal(receiver, globalThis);
});

const WAKE = "https://auth.example.test/health";

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

test("503 with wake_url wakes Auth from the browser and retries once", async () => {
  const calls = [];
  let waking = 0;
  const api = new ApiService({
    baseURL: "https://api.example.test",
    storage: createStorage(),
    fetchImpl: async (url, options) => {
      calls.push({ url: String(url), mode: options?.mode });
      if (String(url) === WAKE) return new Response(null, { status: 200 });
      return calls.filter((c) => c.url.startsWith("https://api")).length === 1
        ? json(503, { error: "Authentication service unavailable", wake_url: WAKE })
        : json(200, { sent: true });
    },
  });
  api.setWakingListener(() => { waking += 1; });
  assert.equal(await api.postAuthMail("a@udf.edu.br"), true);
  assert.deepEqual(calls.map((c) => c.url.split("?")[0]), [
    "https://api.example.test/auth/send-link", WAKE, "https://api.example.test/auth/send-link",
  ]);
  assert.equal(calls[1].mode, "no-cors");
  assert.equal(waking, 1);
});

test("a second 503 after the wake is reported, not retried again", async () => {
  let apiCalls = 0;
  const api = new ApiService({
    baseURL: "https://api.example.test",
    storage: createStorage(),
    fetchImpl: async (url) => {
      if (String(url) === WAKE) return new Response(null, { status: 200 });
      apiCalls += 1;
      return json(503, { error: "unavailable", wake_url: WAKE });
    },
  });
  assert.equal(await api.postAuthMail("a@udf.edu.br"), null);
  assert.equal(apiCalls, 2);
});

test("wake_url that is not an https /health URL is ignored", async () => {
  for (const wake of ["http://auth.example.test/health", "https://evil.example.test/steal", "https://auth.example.test/health?x=1", "nope"]) {
    const urls = [];
    const api = new ApiService({
      baseURL: "https://api.example.test",
      storage: createStorage(),
      fetchImpl: async (url) => { urls.push(String(url)); return json(503, { error: "unavailable", wake_url: wake }); },
    });
    assert.equal(await api.postAuthMail("a@udf.edu.br"), null);
    assert.equal(urls.length, 1, wake);
  }
});

test("validateToken keeps the session when Auth is unavailable (503)", async () => {
  const storage = createStorage({ token: "jwt-123", userEmail: "a@udf.edu.br" });
  const api = new ApiService({
    baseURL: "https://api.example.test",
    storage,
    fetchImpl: async () => json(503, { error: "unavailable" }),
  });
  assert.equal(await api.validateToken("jwt-123", "a@udf.edu.br"), false);
  assert.equal(storage.getItem("token"), "jwt-123");
});

test("validateToken still clears the session on a real denial (403)", async () => {
  const storage = createStorage({ token: "jwt-123" });
  const api = new ApiService({
    baseURL: "https://api.example.test",
    storage,
    fetchImpl: async () => json(403, { error: "Token validation failed" }),
  });
  assert.equal(await api.validateToken("jwt-123", "a@udf.edu.br"), false);
  assert.equal(storage.getItem("token"), null);
});
