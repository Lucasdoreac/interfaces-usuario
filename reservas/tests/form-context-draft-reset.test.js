import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";
import { saveDraftCoordinated } from "../src/utils/draftCreateLock.js";
import { draftSaveFailure } from "../src/utils/draftSaveFailure.js";

// Runs the real provider with a small, deterministic hook harness. Only its JSX
// provider wrapper is replaced; production save/clear logic remains unchanged.
// No DOM, real network, credentials, or extra test dependencies are needed.
function mountProvider({ locks }) {
  const values = new Map([["theme", "dark"]]);
  const localStorage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
  const OLD = "64b7f0c2a1b2c3d4e5f60718";
  const NEW = "64b7f0c2a1b2c3d4e5f60719";
  const calls = [];
  const apiService = {
    getTypes: async () => ({ types: [] }),
    submitEventData: async (data, status, id) => {
      calls.push({ data: { ...data }, status, id });
      if (calls.length === 1) return OLD;
      if (id === OLD) throw Object.assign(new Error("conflict"), { status: 409 });
      return id || NEW;
    },
  };
  const states = [], dependencies = [];
  let cursor = 0, effects = [], context;
  const React = { createElement: (_type, props) => { context = props.value; } };
  const hooks = {
    createContext: () => ({ Provider: {} }),
    useContext: () => context,
    useState(initial) {
      const index = cursor++;
      if (!(index in states)) states[index] = typeof initial === "function" ? initial() : initial;
      return [states[index], (value) => { states[index] = typeof value === "function" ? value(states[index]) : value; }];
    },
    useEffect(fn, deps) {
      const index = cursor++;
      const old = dependencies[index];
      if (!old || deps.some((dep, i) => !Object.is(dep, old[i]))) effects.push(fn);
      dependencies[index] = deps;
    },
    useCallback: (fn) => { cursor++; return fn; },
  };
  let source = readFileSync(new URL("../src/context/FormContext.jsx", import.meta.url), "utf8");
  source = source.replace(/^import React,\s*\{[\s\S]*?\}\s*from "react";\s*/m, "")
    .replace(/^import .*?;\s*/gm, "")
    .replaceAll("export const ", "const ");
  const jsx = /return\s*\(\s*<FormContext\.Provider\s+value=\{\{([\s\S]*?)\}\}\s*>\s*\{children\}\s*<\/FormContext\.Provider>\s*\);/;
  assert.match(source, jsx, "provider wrapper changed: update test harness, not production logic");
  source = source.replace(jsx, "return React.createElement(FormContext.Provider, { value: {$1} }, children);");
  const sandbox = { ...hooks, React, apiService, localStorage, navigator: { locks }, saveDraftCoordinated, draftSaveFailure,
    EventStatus: { DRAFT: "DRAFT" }, formatDateForMongoDB: () => { throw new Error("not used"); },
    console: { error() {} } };
  const Provider = vm.runInNewContext(`${source}\nFormProvider`, sandbox, { filename: "FormContext.jsx" });
  function render() {
    cursor = 0; effects = [];
    Provider({ children: null });
    for (const effect of effects) effect();
    return context;
  }
  return { render, localStorage, calls, OLD, NEW };
}

for (const withLocks of [true, false]) {
  test(`after 409 reset clears the provider ID and creates a new draft (${withLocks ? "with" : "without"} Web Locks)`, async () => {
    let lockCount = 0;
    const locks = withLocks ? { request: async (_name, fn) => { lockCount++; return fn(); } } : undefined;
    const h = mountProvider({ locks });
    let ctx = h.render();
    ctx.handleChange({ target: { name: "tituloEvento", value: "Antigo" } });
    ctx = h.render();
    assert.equal(await ctx.saveDraft(), h.OLD);
    ctx = h.render();
    assert.equal(ctx.eventId, h.OLD);
    assert.equal(h.localStorage.getItem("eventId"), h.OLD);
    assert.equal(await ctx.saveDraft(), null);
    ctx = h.render();
    assert.equal(ctx.saveFailure.kind, "conflict");
    assert.equal(h.calls[1].id, h.OLD);
    await ctx.fillOutFormData("");
    ctx = h.render();
    assert.equal(ctx.eventId, "", "old ID must not survive in provider state");
    assert.equal(h.localStorage.getItem("eventId"), null);
    assert.equal(Object.keys(ctx.formData).length, 0);
    assert.equal(ctx.saveFailure, null);
    assert.equal(h.localStorage.getItem("theme"), "dark");
    ctx.handleChange({ target: { name: "tituloEvento", value: "Novo" } });
    ctx = h.render();
    assert.equal(await ctx.saveDraft(), h.NEW);
    ctx = h.render();
    assert.equal(h.calls[2].id, "", "new save must create, not update the submitted event");
    assert.equal(h.calls[2].data.tituloEvento, "Novo");
    assert.equal(ctx.eventId, h.NEW);
    assert.equal(h.localStorage.getItem("eventId"), h.NEW);
    assert.equal(await ctx.saveDraft(), h.NEW);
    assert.equal(h.calls[3].id, h.NEW, "subsequent save updates the new draft");
    assert.equal(lockCount, withLocks ? 2 : 0);
  });
}
