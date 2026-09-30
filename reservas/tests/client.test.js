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
