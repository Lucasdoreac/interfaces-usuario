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

test("dark theme: the page background in App.scss is the one measured here", () => {
  assert.match(css, /body\.dark \{?[^{}]*\{[^}]*background-color:\s*#1d1d1d|body\.dark\s*\{[^}]*background-color:\s*#1d1d1d/);
});

test("dark theme: outline buttons use a blue that reaches 4.5:1 on the dark background (WCAG 1.4.3)", () => {
  const color = css.match(/body\.dark \.btn-outline-primary\s*\{[^}]*?--bs-btn-color:\s*(#[0-9a-fA-F]{6})/)?.[1];
  assert.ok(color, "the dark outline-button colour is missing");
  assert.ok(ratio(color, DARK_BACKGROUND) >= 4.5, `${color} is ${ratio(color, DARK_BACKGROUND).toFixed(2)}:1`);
});

test("dark theme: the active navbar link reaches 4.5:1 on the dark navbar", () => {
  const color = css.match(/body\.dark #nav a\.nav-link\.active\s*\{[^}]*?color:\s*(#[0-9a-fA-F]{6})/)?.[1];
  assert.ok(color, "the dark active-link colour is missing");
  assert.ok(ratio(color, DARK_BACKGROUND) >= 4.5, `${color} is ${ratio(color, DARK_BACKGROUND).toFixed(2)}:1`);
});

const especialista = css.match(/body\.dark \.sistema-especialista\s*\{[\s\S]*?\n\}\n/)?.[0] ?? "";
const corDe = (regra) => especialista.match(new RegExp(`${regra}\\s*\\{[^}]*?(?:^|[\\s;{])color:\\s*(#[0-9a-fA-F]{6})`, "m"))?.[1];

test("dark theme: the expert-system page redraws table text, links, code and fields", () => {
  assert.ok(especialista, "the dark rules for .sistema-especialista are missing");
  assert.match(especialista, /--bs-table-color:\s*#fff/);
  assert.match(especialista, /--bs-table-bg:\s*#1d1d1d/);
  for (const [nome, regra] of [["links", "a"], ["code", "code"]]) {
    const cor = corDe(regra);
    assert.ok(cor, `${nome}: colour missing`);
    assert.ok(ratio(cor, DARK_BACKGROUND) >= 4.5, `${nome} ${cor} is ${ratio(cor, DARK_BACKGROUND).toFixed(2)}:1`);
  }
  assert.match(especialista, /\.form-control,\s*\.form-select\s*\{[^}]*background-color:\s*#1d1d1d;[^}]*color:\s*#fff/);
});

test("a página /sistema-especialista não cresce com o hover do card global", () => {
  const regra = css.match(/main\.card:has\(\.sistema-especialista\)[\s\S]*?\{[^}]*\}/)?.[0] ?? "";
  assert.ok(regra, "a regra que neutraliza o scale do card está ausente");
  for (const estado of [":hover", ":focus", ":active"]) assert.ok(regra.includes(`main.card:has(.sistema-especialista)${estado}`), estado);
  assert.match(regra, /transform:\s*none\s*!important/);
  const card = readFileSync(new URL("../src/index.scss", import.meta.url), "utf8");
  assert.match(card, /\.card:hover[\s\S]*?transform:\s*scale\(1\.01\)\s*!important/, "as outras telas mantêm o comportamento do app");
});

test("as seções de /sistema-especialista têm altura do conteúdo, não 93vh como a regra global do app", () => {
  const regra = css.match(/\.sistema-especialista section\s*\{[^}]*\}/)?.[0] ?? "";
  assert.match(regra, /height:\s*auto\s*!important/, "sem esta regra, cada <section> fica com 93vh e uma cobre a outra");
  const navbar = readFileSync(new URL("../src/components/Navbar/Navbar.scss", import.meta.url), "utf8");
  assert.match(navbar, /section\s*\{\s*height:\s*93vh;/, "as outras telas mantêm a regra global");
});
