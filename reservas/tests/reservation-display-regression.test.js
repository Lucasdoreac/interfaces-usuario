import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { ApiService } from "../src/services/client.js";
import { formatDateForMongoDB, formatReservation } from "../src/utils/dateUtils.js";

test("API ISO and HTTP GMT timestamps preserve instant and render in the picker's zone", async () => {
  process.env.TZ = "America/Sao_Paulo";
  const selected = new Date(2026, 9, 17, 8, 0);
  assert.equal(formatDateForMongoDB(selected), "2026-10-17T11:00:00.000Z");
  for (const startAt of ["2026-10-17T11:00:00.000Z", "Sat, 17 Oct 2026 11:00:00 GMT"]) {
    const api = new ApiService({baseURL: "https://example.test", storage: null, fetchImpl: async () => new Response(JSON.stringify({ startAt, endAt: "Sat, 17 Oct 2026 14:00:00 GMT" }), {status: 200, headers: {"content-type":"application/json"}})});
    const reservation = await api.getEventsReservations("synthetic");
    assert.equal(reservation.startAt, startAt);
    assert.deepEqual(formatReservation(reservation.startAt, reservation.endAt), {day: "17/10/2026", hours: "08:00 - 11:00"});
  }
});

test("day and time follow the same zone, including midnight and missing dates", () => {
  process.env.TZ = "America/Sao_Paulo";
  assert.deepEqual(formatReservation("2026-10-18T02:30:00Z", "2026-10-18T04:00:00Z"), {day: "17/10/2026", hours: "23:30 - 01:00 (18/10/2026)"});
  assert.deepEqual(formatReservation(null, null), {day: "Indefinido", hours: "Indefinido"});
  process.env.TZ = "UTC";
  assert.deepEqual(formatReservation("2026-10-18T02:30:00Z", "2026-10-18T04:00:00Z"), {day: "17/10/2026", hours: "23:30 - 01:00 (18/10/2026)"});
});

test("MyEvents uses the tested formatter", () => {
  const source = readFileSync(new URL("../src/pages/meus-eventos/MyEvents.jsx", import.meta.url), "utf8");
  assert.match(source, /formatReservation\(reservation\?\.startAt, reservation\?\.endAt\)/);
  assert.doesNotMatch(source, /getUTCHours/);
});
