import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const organizer = read("../src/pages/organizer/Organizer.jsx");
const input = organizer.match(/<input[\s\S]*?\/>/)?.[0] ?? "";

test("the e-mail field has a label, an id, the right type and autofill hints", () => {
  const id = input.match(/\bid="([^"]+)"/)?.[1];
  assert.ok(id, "the input needs an id");
  assert.match(organizer, new RegExp(`<label htmlFor="${id}"`));
  assert.match(input, /type="email"/);
  assert.match(input, /autoComplete="email"/);
  assert.match(input, /\brequired\b/);
});

test("an error is announced and tied to the field", () => {
  assert.match(input, /aria-invalid=/);
  const describedBy = input.match(/aria-describedby=\{[^}]*"([^"]+)"/)?.[1];
  assert.ok(describedBy, "the input needs aria-describedby for its error");
  assert.match(organizer, new RegExp(`id="${describedBy}"[^>]*role="alert"|role="alert"[^>]*id="${describedBy}"`));
  assert.doesNotMatch(organizer, /color:\s*"red"/);
});

test("the notice region is always mounted, not created with its text", () => {
  assert.match(organizer, /<div role="status" aria-live="polite"/);
  assert.doesNotMatch(organizer, /\{notice && /);
});

test("the waking notice of the private route lives inside a status region that is always there while loading", () => {
  const route = read("../src/PrivateRoute.jsx");
  assert.match(route, /role="status"\s+aria-live="polite"\s+aria-busy="true"/);
  assert.doesNotMatch(route, /\{waking && <p role="status"/);
});

test("the spinner is hidden from assistive technology and carries a text label", () => {
  const loading = read("../src/components/Loading/index.jsx");
  assert.match(loading, /className="lds-roller" aria-hidden="true"/);
  assert.match(loading, /className="visually-hidden"/);
});

// WCAG AA, normal text: 4.5:1.
const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (fg, bg = "#ffffff") => {
  const [a, b] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
};

test("form error and notice colors reach 4.5:1 on white", () => {
  const css = read("../src/index.scss");
  for (const selector of [".form-error", ".form-notice"]) {
    const color = css.match(new RegExp(`${selector.replace(".", "\\.")}\\s*\\{[^}]*?color:\\s*(#[0-9a-fA-F]{6})`))?.[1];
    assert.ok(color, `${selector} must set a hex color in index.scss`);
    assert.ok(ratio(color) >= 4.5, `${selector} ${color} is ${ratio(color).toFixed(2)}:1`);
  }
});
