import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const styles = readFileSync(new URL("../src/components/Navbar/Navbar.scss", import.meta.url), "utf8");
const variable = (name) => styles.match(new RegExp(`\\$${name}:\\s*(#[0-9a-fA-F]{3,6});`))?.[1];
const resolve = (value) => (value.startsWith("$") ? variable(value.slice(1)) : value);
const expand = (hex) => (hex.length === 4 ? `#${[...hex.slice(1)].map((c) => c + c).join("")}` : hex);

const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(expand(hex).slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (fg, bg) => {
  const [a, b] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
};

// Colour set for `selector` by the top-level rules (outside @media); the last declaration wins.
const ruleColor = (selector) => {
  const top = styles.replace(/@media[^{]*\{(?:[^{}]*\{[^{}]*\}\s*)*\}/g, "").replace(/\/\/[^\n]*/g, "");
  let color;
  for (const [, list, body] of top.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const selectors = list.split(",").map((s) => s.trim());
    const found = body.match(/(?:^|[;\s])color:\s*([^;]+);/)?.[1].trim();
    if (selectors.includes(selector) && found) color = found;
  }
  return color;
};

const stops = styles.match(/linear-gradient\(45deg,\s*(\$[\w-]+),\s*(\$[\w-]+)\)/).slice(1).map(resolve);
const darkest = stops.sort((a, b) => luminance(a) - luminance(b))[0];

test("the logo text, in every link state, is the light colour (not the a:link primary)", () => {
  for (const selector of [".logo", ".logo a", ".logo a:link", ".logo a:visited", ".logo a:active", ".logo a:hover"]) {
    const color = ruleColor(selector);
    assert.ok(color, `${selector} must set a colour`);
    assert.equal(resolve(color).toLowerCase(), "#fff", `${selector} colour is ${color}`);
  }
});

test("no media query recolours the logo", () => {
  const media = [...styles.matchAll(/@media[^{]*\{([\s\S]*?)\n\}/g)].map((m) => m[1]).join("\n");
  assert.doesNotMatch(media, /\.logo/);
});

test("the logo text reaches 4.5:1 against the darkest gradient stop it overlaps", () => {
  const color = resolve(ruleColor(".logo a:link"));
  const value = ratio(color, darkest);
  console.log(`logo ${color} on ${darkest}: ${value.toFixed(2)}:1`);
  assert.ok(value >= 4.5, `${color} on ${darkest} is ${value.toFixed(2)}:1`);
});
