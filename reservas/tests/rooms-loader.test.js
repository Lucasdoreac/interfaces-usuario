import assert from "node:assert/strict";
import { test } from "node:test";
import { createRoomsLoader } from "../src/components/infinite-scroll-rooms/roomPagination.js";

const room = (id) => ({ id, name: `Sala ${id}` });

function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

function setup(fetchPage) {
  const box = { state: null };
  const loader = createRoomsLoader({ fetchPage, onChange: (s) => { box.state = s; } });
  return { box, loader };
}

test("a response for an old filter does not overwrite rooms or advance the pagination", async () => {
  const pending = { old: deferred(), next: deferred() };
  const { box, loader } = setup((page, filter) => pending[filter.search].promise);
  const first = loader.setFilter({ search: "old" });
  const second = loader.setFilter({ search: "next" });
  pending.next.resolve({ data: [room("novo")], pagination: { total_pages: 1 } });
  await second;
  pending.old.resolve({ data: [room("velho-1"), room("velho-2")], pagination: { total_pages: 9 } });
  await first;
  assert.deepEqual(box.state.rooms.map((r) => r.id), ["novo"]);
  assert.equal(box.state.page, 1);
  assert.equal(box.state.hasMore, false);
  assert.equal(box.state.isLoading, false);
});

test("an error from an old filter is ignored", async () => {
  const pending = { old: deferred(), next: deferred() };
  const { box, loader } = setup((page, filter) => pending[filter.search].promise);
  const first = loader.setFilter({ search: "old" });
  const second = loader.setFilter({ search: "next" });
  pending.old.reject(new Error("falhou"));
  await first;
  assert.equal(box.state.error, null);
  pending.next.resolve({ data: [room("a")], pagination: { total_pages: 1 } });
  await second;
  assert.deepEqual(box.state.rooms.map((r) => r.id), ["a"]);
});

test("a second load while one is in flight is ignored even right after a filter change", async () => {
  let calls = 0;
  const gate = deferred();
  const { loader } = setup(() => { calls += 1; return gate.promise; });
  const first = loader.setFilter({ search: "" });
  loader.loadMore();
  loader.loadMore();
  gate.resolve({ data: [room("a")], pagination: { total_pages: 3 } });
  await first;
  assert.equal(calls, 1);
});

test("retry refetches page 1 for the current filter after a failed first load", async () => {
  const seen = [];
  let fail = true;
  const { box, loader } = setup(async (page, filter) => {
    seen.push([page, filter.search]);
    if (fail) throw { response: { data: { error: "indisponível" } } };
    return { data: [room("a")], pagination: { total_pages: 1 } };
  });
  await loader.setFilter({ search: "bloco" });
  assert.equal(box.state.error, "indisponível");
  fail = false;
  await loader.retry();
  assert.deepEqual(seen, [[1, "bloco"], [1, "bloco"]]);
  assert.equal(box.state.error, null);
  assert.deepEqual(box.state.rooms.map((r) => r.id), ["a"]);
});

test("retry after a failed next page appends that page instead of restarting", async () => {
  let call = 0;
  const { box, loader } = setup(async (page) => {
    call += 1;
    if (call === 2) throw new TypeError("fetch failed");
    return { data: [room(`p${page}`)], pagination: { total_pages: 2 } };
  });
  await loader.setFilter({ search: "" });
  await loader.loadMore();
  assert.equal(box.state.error, "Erro ao carregar salas disponíveis.");
  await loader.retry();
  assert.deepEqual(box.state.rooms.map((r) => r.id), ["p1", "p2"]);
  assert.equal(box.state.error, null);
});

test("the error state offers a retry button wired to the loader", async () => {
  const { readFileSync } = await import("node:fs");
  const source = readFileSync(new URL("../src/components/infinite-scroll-rooms/InfiniteScrollRooms.jsx", import.meta.url), "utf8");
  assert.match(source, /<button type="button"[^>]*onClick=\{\(\) => loader\.retry\(\)\}>\s*Tentar novamente/);
  assert.match(source, /role="alert"/);
});
