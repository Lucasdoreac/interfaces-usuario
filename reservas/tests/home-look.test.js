import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

// The org's main renders the Home with an outline "ORGANIZADOR" button inside a white-framed card;
// the consolidation must not change that look by accident.
test("home keeps the org main look: outline organizer button", () => {
  const home = read("../src/pages/Home/Home.jsx");
  assert.match(home, /className="btn btn-outline-primary btn-lg"[\s\S]*?ORGANIZADOR/);
});

test("the card keeps its white frame", () => {
  const css = read("../src/index.scss");
  assert.match(css, /\.card\s*\{[^}]*border-color:\s*#fff\s*!important/);
});

test("dark theme: the outline button blue reaches 4.5:1 on the dark background (WCAG 1.4.3)", () => {
  const css = read("../src/App.scss");
  const color = css.match(/body\.dark \.btn-outline-primary\s*\{[^}]*?--bs-btn-color:\s*(#[0-9a-fA-F]{6})/)?.[1];
  assert.ok(color, "the dark outline-button colour is missing");
  const lum = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const [a, b] = [lum(color), lum("#1d1d1d")].sort((x, y) => y - x);
  assert.ok((a + 0.05) / (b + 0.05) >= 4.5, `${color} is ${((a + 0.05) / (b + 0.05)).toFixed(2)}:1`);
});
