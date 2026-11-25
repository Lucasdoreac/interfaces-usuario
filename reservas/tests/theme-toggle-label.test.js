import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("theme toggle label is in Portuguese like the rest of the interface", () => {
  const button = read("../src/components/Button/ThemeToggleButton.jsx");
  assert.doesNotMatch(button, /Switch to|Dark Mode|Light Mode/);
  assert.match(button, /Ativar modo escuro/);
  assert.match(button, /Ativar modo claro/);
});
