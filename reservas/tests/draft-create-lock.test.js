import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { clearStoredDraftId, saveDraftCoordinated } from "../src/utils/draftCreateLock.js";

const ID = "64b7f0c2a1b2c3d4e5f60718";

function createStorage(values = {}) {
  return {
    values: { ...values },
    getItem(key) { return this.values[key] ?? null; },
    setItem(key, value) { this.values[key] = value; },
    removeItem(key) { delete this.values[key]; },
  };
}

// Lock exclusivo que serializa os pedidos, como navigator.locks entre separadores.
function fakeLocks() {
  let tail = Promise.resolve();
  return {
    request(_name, callback) {
      const run = tail.then(() => callback());
      tail = run.catch(() => {});
      return run;
    },
  };
}

function fakeApi(storage) {
  const calls = { create: 0, update: [] };
  return {
    calls,
    send: async (id) => {
      await new Promise((resolve) => setTimeout(resolve, 5));
      if (!id) { calls.create += 1; return ID; }
      calls.update.push(id);
      return id;
    },
  };
}

test("two tabs saving without an eventId create exactly one draft; the second updates it", async () => {
  const storage = createStorage();
  const api = fakeApi(storage);
  const locks = fakeLocks();
  const tab = () => saveDraftCoordinated({ eventId: "", storage, locks, send: api.send });
  const [a, b] = await Promise.all([tab(), tab()]);
  assert.equal(api.calls.create, 1);
  assert.deepEqual(api.calls.update, [ID]);
  assert.equal(a, ID);
  assert.equal(b, ID);
  assert.equal(storage.getItem("eventId"), ID);
});

test("a state eventId updates directly without taking the lock", async () => {
  const storage = createStorage();
  const api = fakeApi(storage);
  const locks = { request() { throw new Error("lock should not be used"); } };
  const id = await saveDraftCoordinated({ eventId: ID, storage, locks, send: api.send });
  assert.equal(id, ID);
  assert.equal(api.calls.create, 0);
  assert.deepEqual(api.calls.update, [ID]);
});

test("an invalid stored id is ignored and a draft is created", async () => {
  const storage = createStorage({ eventId: "not-an-id" });
  const api = fakeApi(storage);
  await saveDraftCoordinated({ eventId: "", storage, locks: fakeLocks(), send: api.send });
  assert.equal(api.calls.create, 1);
  assert.equal(storage.getItem("eventId"), ID);
});

test("without navigator.locks it falls back to a plain create", async () => {
  const storage = createStorage();
  const api = fakeApi(storage);
  const id = await saveDraftCoordinated({ eventId: "", storage, locks: undefined, send: api.send });
  assert.equal(id, ID);
  assert.equal(api.calls.create, 1);
  assert.equal(storage.getItem("eventId"), ID);
});

test("a failed create releases the lock and stores nothing", async () => {
  const storage = createStorage();
  const locks = fakeLocks();
  await assert.rejects(
    saveDraftCoordinated({ eventId: "", storage, locks, send: async () => { throw new Error("falhou"); } }),
    /falhou/,
  );
  assert.equal(storage.getItem("eventId"), null);
  const api = fakeApi(storage);
  await saveDraftCoordinated({ eventId: "", storage, locks, send: api.send });
  assert.equal(api.calls.create, 1);
});

test("after the final submission a coordinated create with empty state creates, it does not reuse the submitted id", async () => {
  const storage = createStorage({ eventId: ID });
  clearStoredDraftId(storage);
  assert.equal(storage.getItem("eventId"), null);
  const api = fakeApi(storage);
  await saveDraftCoordinated({ eventId: "", storage, locks: fakeLocks(), send: api.send });
  assert.equal(api.calls.create, 1);
  assert.deepEqual(api.calls.update, []);
});

test("without clearing, a second tab would reuse the submitted id (the gap the clear closes)", async () => {
  const storage = createStorage({ eventId: ID });
  const api = fakeApi(storage);
  await saveDraftCoordinated({ eventId: "", storage, locks: fakeLocks(), send: api.send });
  assert.equal(api.calls.create, 0);
  assert.deepEqual(api.calls.update, [ID]);
});

test("the final submission clears the stored id only after the approval request succeeds", () => {
  const source = readFileSync(new URL("../src/pages/event-confirm-data/EventConfirmData.jsx", import.meta.url), "utf8");
  const submit = source.indexOf("submitEventForApproval(");
  const guard = source.indexOf("if (!event_submission)");
  const clear = source.indexOf("clearStoredDraftId(localStorage)");
  const nav = source.indexOf("navigate(`/event/confirmation");
  assert.ok(submit > 0 && guard > submit, "submit then guard");
  assert.ok(clear > guard, "clear only after the success guard");
  assert.ok(nav > clear, "clear before navigating");
});
