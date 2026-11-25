import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const navbar = read("../src/components/Navbar/Navbar.jsx");
const styles = read("../src/components/Navbar/Navbar.scss");

test("the mobile menu button opens the state the stylesheet already defines", () => {
  // Below 800px the links are hidden until #nav gets .nav-visible.
  assert.match(styles, /&\.nav-visible/);
  assert.match(navbar, /"nav-visible"/, "the component never applies .nav-visible");
  assert.match(navbar, /<button[^>]*id="menu"[^>]*onClick=/s, "#menu has no click handler");
});

test("the mobile menu button announces its state to assistive technology", () => {
  assert.match(navbar, /aria-expanded=/);
  assert.match(navbar, /aria-controls="nav-links"/);
  assert.match(navbar, /id="nav-links"/);
});

test("the collapsed navbar is never shorter than its 4em contents", () => {
  assert.match(styles, /min-height:\s*4em/, "#nav can clip its 4em navigation row");
});

test("the menu icon does not depend on FontAwesome, which the app never loads", () => {
  assert.doesNotMatch(navbar, /fa-bars/);
});

test("Bootstrap is imported after the app's own CSS, as in the previous CRA entry", () => {
  const root = read("../app/root.jsx");
  const order = [...root.matchAll(/^import\s+(?:[\w{}\s,*]+\s+from\s+)?"([^"]+)";/gm)].map((m) => m[1]);
  const at = (needle) => order.findIndex((spec) => spec.includes(needle));
  assert.ok(at("bootstrap") > at("index.scss") && at("bootstrap") > at("App.scss") && at("bootstrap") > at("Navbar"),
    `bootstrap must come after index.scss, App.scss and the Navbar; got ${JSON.stringify(order)}`);
});
