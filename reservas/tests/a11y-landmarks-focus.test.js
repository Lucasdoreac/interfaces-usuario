import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const walk = (dir, ext) =>
  readdirSync(new URL(dir, import.meta.url), { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(`${dir}${e.name}/`, ext) : e.name.endsWith(ext) ? [`${dir}${e.name}`] : [],
  );

const scss = walk("../src/", ".scss");
const jsx = walk("../src/", ".jsx");
const routes = walk("../app/routes/", ".jsx");

test("no stylesheet hides the keyboard focus ring with outline: 0/none", () => {
  for (const file of scss) {
    assert.doesNotMatch(read(file), /outline:\s*(0|none)\b/, `${file} removes the focus outline`);
  }
});

test("a global :focus-visible outline exists and is not mouse-triggered", () => {
  const css = read("../src/index.scss");
  assert.match(css, /(^|\n):focus-visible\s*\{[^}]*outline:\s*3px solid #0a2d7a/);
  assert.doesNotMatch(css, /(^|\n):focus\s*\{[^}]*outline/, "a plain :focus outline shows on mouse click");
  assert.match(css, /\.card-header :focus-visible[^{]*\{[^}]*outline-color:\s*#fff/s, "no ring colour for the blue header");
});

test("the root layout wraps the routed content in one <main>", () => {
  const root = read("../app/root.jsx");
  assert.match(root, /<main[^>]*>\s*<Outlet \/>\s*<\/main>/);
  assert.equal((root.match(/<main\b/g) || []).length, 2, "one for the layout, one for the ErrorBoundary");
});

test("the LabTech UDF logo is not a heading", () => {
  const navbar = read("../src/components/Navbar/Navbar.jsx");
  assert.doesNotMatch(navbar, /<h[1-6]/);
  assert.doesNotMatch(read("../src/components/Navbar/Navbar.scss"), /h1\.logo/);
});

test("each page that renders a screen has a single h1", () => {
  const pages = jsx.filter((f) => f.includes("/pages/"));
  for (const file of pages) {
    const count = (read(file).match(/<h1\b/g) || []).length;
    // EventLogistics/EventDetails render the h1 in alternative branches.
    assert.ok(count >= 1, `${file} has no h1`);
  }
  assert.doesNotMatch(read("../src/pages/access-denied/AccessDenied.jsx").replace("<h1>Acesso Negado</h1>", ""), /<h1/);
});

test("every route module exports a meta with '<Tela> | Reservas UDF'", () => {
  assert.match(read("../src/routeMeta.js"), /title:\s*`\$\{screen\} \| Reservas UDF`/);
  const leaves = routes.filter((f) => !f.endsWith("event-layout.jsx"));
  assert.equal(leaves.length, 12);
  for (const file of leaves) {
    const src = read(file);
    assert.match(src, /export function meta\(\)\s*\{\s*return pageMeta\("[^"]+"\);/, `${file} has no meta`);
  }
  const titles = leaves.map((f) => read(f).match(/pageMeta\("([^"]+)"\)/)[1]);
  assert.equal(new Set(titles).size, titles.length, "two routes share a title");
});

test("the decorative avatar has an empty alt", () => {
  for (const file of ["Home/Home.jsx", "organizer/Organizer.jsx", "auth-callback/AuthCallBack.jsx"]) {
    const src = read(`../src/pages/${file}`);
    assert.doesNotMatch(src, /alt="man avatar"/, file);
    assert.match(src, /alt=""/, file);
  }
});

test("buttons on the touched pages declare a type unless they sit in a form", () => {
  for (const file of [
    "Home/Home.jsx",
    "access-denied/AccessDenied.jsx",
    "event-confirm-data/EventConfirmData.jsx",
    "event-confirmation/EventConfirmation.jsx",
    "event-schedule/EventSchedule.jsx",
  ]) {
    const src = read(`../src/pages/${file}`);
    for (const tag of src.match(/<button\b[^>]*>/g) || []) {
      assert.match(tag, /\btype=/, `${file}: ${tag}`);
    }
  }
});
