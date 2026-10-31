import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("../src/App.scss", import.meta.url), "utf8");
const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (fg, bg) => {
  const [a, b] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
};
const DARK_BACKGROUND = "#1d1d1d"; // body.dark background in App.scss

test("dark theme: the navbar background in App.scss is the one measured here", () => {
  assert.match(css, /body\.dark #nav\s*\{[^}]*background-color:\s*#1d1d1d/);
});

test("dark theme: navbar links and the menu icon are light text, 4.5:1 on the dark navbar (WCAG 1.4.3)", () => {
  const rule = css.match(/body\.dark #nav a\.nav-link:not\(\.active\),\s*body\.dark #nav \.btn-nav\s*\{[^}]*?color:\s*(#[0-9a-fA-F]{6})/);
  assert.ok(rule, "the dark navbar link/menu colour rule is missing");
  assert.ok(ratio(rule[1], DARK_BACKGROUND) >= 4.5, `${rule[1]} is ${ratio(rule[1], DARK_BACKGROUND).toFixed(2)}:1`);
});
