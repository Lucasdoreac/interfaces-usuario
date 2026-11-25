import assert from "node:assert/strict";
import { test } from "node:test";
import { ApiService } from "../src/services/client.js";
import { readFileSync } from "node:fs";
import { hasInvalidEventIdParam, isEventId } from "../src/utils/eventId.js";

const GOOD = "507f1f77bcf86cd799439011";
const BAD = ["../reservations?", "../../auth/validate#", `${GOOD}/../x`, `${GOOD}?x=1`, "abc", "", "null", "undefined", `${GOOD}0`, 12, null, undefined];

function api(urls) {
  return new ApiService({
    baseURL: "https://api.example.test",
    storage: { getItem: () => null, setItem() {}, clear() {} },
    fetchImpl: async (url) => {
      urls.push(String(url));
      return new Response(JSON.stringify({ eventId: GOOD }), { status: 200, headers: { "content-type": "application/json" } });
    },
  });
}

test("only 24-hex ids are event ids", () => {
  assert.equal(isEventId(GOOD), true);
  assert.equal(isEventId(GOOD.toUpperCase()), true);
  for (const value of BAD) assert.equal(isEventId(value), false, String(value));
});

test("a crafted eventId never reaches the network", async () => {
  for (const value of BAD.filter((v) => v)) { // '' / null mean "new event" in submitEventData
    const urls = [];
    const service = api(urls);
    await assert.rejects(service.submitEventData({}, "draft", value), /Evento inválido/);
    await assert.rejects(service.submitEventForApproval(value, {}), /Evento inválido/);
    assert.deepEqual(urls, [], `request sent for ${String(value)}`);
  }
  await assert.rejects(api([]).submitEventForApproval("", {}), /Evento inválido/);
});

test("a valid id keeps the paths the API expects", async () => {
  const urls = [];
  const service = api(urls);
  await service.submitEventData({}, "draft", GOOD);
  await service.submitEventData({}, "draft", null);
  await service.submitEventForApproval(GOOD, {});
  assert.deepEqual(urls, [
    `https://api.example.test/events/${GOOD}`,
    "https://api.example.test/events",
    `https://api.example.test/events/${GOOD}/submit`,
  ]);
});

test("a malformed eventId in the URL is detected at the entry point, an absent one is not", () => {
  assert.equal(hasInvalidEventIdParam(`?eventId=${GOOD}`), false);
  assert.equal(hasInvalidEventIdParam(""), false);
  assert.equal(hasInvalidEventIdParam("?other=1"), false);
  for (const bad of ["../reservations?", "abc", "", "null"]) {
    assert.equal(hasInvalidEventIdParam(`?eventId=${encodeURIComponent(bad)}`), true, bad);
  }
});

test("the event layout reports an invalid eventId instead of rendering the pages", () => {
  const source = readFileSync(new URL("../app/routes/event-layout.jsx", import.meta.url), "utf8");
  assert.match(source, /hasInvalidEventIdParam\(search\)/);
  assert.match(source, /Evento inválido/);
});
