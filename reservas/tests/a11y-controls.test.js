import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

// Clickable <span>/<div>/<h*> are not focusable and not announced as controls.
const CLICKABLE_NON_CONTROL = /<(span|div|h[1-6]|p|li)\b[^>]*\bonClick=/s;

// The wizard's steps still carry the old pattern; they are the follow-up (listed so it shrinks, never grows).
const FOLLOW_UP = [
  "event-basic-info/EventBasicInfo.jsx", "event-confirm-data/EventConfirmData.jsx", "event-details/EventDetails.jsx",
  "event-logistics/EventLogistics.jsx", "event-schedule/EventSchedule.jsx", "event-type-selection/EventTypeSelection.jsx",
];
const PUBLIC = [
  "../src/components/Navbar/Navbar.jsx", "../src/pages/organizer/Organizer.jsx", "../src/pages/Home/Home.jsx",
  "../src/pages/access-denied/AccessDenied.jsx", "../src/pages/auth-callback/AuthCallBack.jsx",
];

test("public screens have no clickable span/div/heading", () => {
  const offenders = PUBLIC.filter((file) => CLICKABLE_NON_CONTROL.test(read(file)));
  assert.deepEqual(offenders, []);
});

test("the navbar logo and link are real links", () => {
  const navbar = read("../src/components/Navbar/Navbar.jsx");
  assert.match(navbar, /import \{[^}]*\bLink\b[^}]*\} from ['"]react-router['"]/);
  assert.match(navbar, /<Link to="\/"/);
  assert.match(navbar, /<Link[^>]*to="\/organizer"/);
});

test("'Voltar' is a button component with a visible label, not an icon in a span", () => {
  const back = read("../src/components/BackButton/index.jsx");
  assert.match(back, /<button type="button"/);
  assert.match(back, /aria-hidden="true"/);
  for (const file of ["../src/pages/organizer/Organizer.jsx", "../src/pages/auth-callback/AuthCallBack.jsx"]) {
    const source = read(file);
    assert.match(source, /<BackButton /, `${file} does not use BackButton`);
    assert.doesNotMatch(source, /<h5>Voltar<\/h5>/, `${file} still has the heading-as-button`);
  }
});

test("the wizard's remaining span-onClick 'Voltar' stays in the follow-up list", () => {
  for (const file of FOLLOW_UP) {
    assert.match(read(`../src/pages/${file}`), /<span\b[^>]*\bonClick=/s, `${file} was fixed: remove it from FOLLOW_UP`);
  }
});
