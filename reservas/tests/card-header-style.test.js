import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

// A rule that styles a class shared by many screens must live in the global
// stylesheet: a route's own stylesheet only loads with that route.
test("the blue card header is defined globally, not in the organizer page's stylesheet", () => {
  const index = read("../src/index.scss");
  const rule = index.match(/\.card-header\s*\{[^}]*\}/)?.[0] ?? "";
  assert.match(rule, /background-color:\s*#0a2d7a\s*!important/, "index.scss must style .card-header");
  assert.match(rule, /color:\s*#fff\s*!important/);
  // The header has no border: this declaration must come after the border-width/color lines
  // above it in the same rule, which it used to override from Organizer.scss.
  assert.ok(rule.lastIndexOf("border: 0 !important") > rule.lastIndexOf("border-color"),
    "the rule must end with border: 0 !important");
  assert.doesNotMatch(read("../src/pages/organizer/Organizer.scss"), /\.card-header\s*\{/,
    "Organizer.scss must not carry the shared .card-header rule");
});

function scssFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? scssFiles(new URL(`${entry.name}/`, dir)) : /\.scss$/.test(entry.name) ? [new URL(entry.name, dir)] : []);
}

// A top-level .card-header rule in a page stylesheet applies to every screen once that route has
// loaded; the access-denied page only nests one under its own section, which is scoped.
test("no page stylesheet restyles the shared .card-header", () => {
  const pages = scssFiles(new URL("../src/pages/", import.meta.url));
  assert.ok(pages.length > 0, "the scan must find the page stylesheets");
  const offenders = pages
    .filter((file) => /^\.card-header\s*[{,]/m.test(readFileSync(file, "utf8")))
    .map((file) => file.pathname.split("/src/pages/")[1]);
  assert.deepEqual(offenders, []);
});
