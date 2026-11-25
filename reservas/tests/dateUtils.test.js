import test from "node:test";
import assert from "node:assert/strict";
import { formatDateForMongoDB } from "../src/utils/dateUtils.js";

test("preserves the selected São Paulo time when serializing to UTC", () => {
  process.env.TZ = "America/Sao_Paulo";
  const selectedAtEleven = new Date("2026-10-17T14:00:00.000Z");

  assert.equal(selectedAtEleven.getHours(), 11);
  assert.equal(formatDateForMongoDB(selectedAtEleven), "2026-10-17T14:00:00.000Z");
});
