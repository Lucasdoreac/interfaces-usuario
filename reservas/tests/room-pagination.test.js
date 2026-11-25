import assert from "node:assert/strict";
import { test } from "node:test";
import { hasMoreRoomPages, roomLoadErrorMessage } from "../src/components/infinite-scroll-rooms/roomPagination.js";

test("continues only when the current page has rooms and another page is declared", () => {
  assert.equal(hasMoreRoomPages([{ id: "room-1" }], { total_pages: 2 }, 1), true);
  assert.equal(hasMoreRoomPages([{ id: "room-1" }], { total_pages: 1 }, 1), false);
});

test("stops pagination for empty pages or missing pagination metadata", () => {
  assert.equal(hasMoreRoomPages([], { total_pages: 3 }, 1), false);
  assert.equal(hasMoreRoomPages([{ id: "room-1" }], undefined, 1), false);
  assert.equal(hasMoreRoomPages([{ id: "room-1" }], { total_pages: "3" }, 1), false);
});

test("uses the API error when available and tolerates network errors without a response", () => {
  assert.equal(roomLoadErrorMessage({ response: { data: { error: "API indisponível" } } }), "API indisponível");
  assert.equal(roomLoadErrorMessage(new TypeError("fetch failed")), "Erro ao carregar salas disponíveis.");
});
