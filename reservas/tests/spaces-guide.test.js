import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("public space guide is routed and reachable from the navigation and home", () => {
  assert.match(read("../app/routes.js"), /route\("espacos", "routes\/espacos\.jsx"\)/);
  assert.match(read("../src/components/Navbar/Navbar.jsx"), /to="\/espacos"/);
  assert.match(read("../src/pages/Home/Home.jsx"), /navigate\("\/espacos"\)/);
});

test("guide preserves the official external request path and does not claim to reserve", () => {
  const page = read("../src/pages/espacos/Espacos.jsx");
  assert.match(page, /https:\/\/forms\.cloud\.microsoft\/r\/xHUxLS9yss/);
  assert.match(page, /três dias úteis/);
  assert.match(page, /confirmação formal por e-mail/);
  assert.match(page, /não cria nem/);
  assert.match(page, /noopener noreferrer/);
});
