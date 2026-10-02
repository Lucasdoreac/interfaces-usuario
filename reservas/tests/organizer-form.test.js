import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const source = readFileSync(new URL("../src/pages/organizer/Organizer.jsx", import.meta.url), "utf8");

test("#34 pressing Enter in the e-mail field submits the login form", () => {
  // Enter submits a form only when the field and a submit button share one.
  const form = source.match(/<form onSubmit=\{sendEmail\}[^>]*>([\s\S]*?)<\/form>/);
  assert.ok(form, "the e-mail field must be inside a <form onSubmit={sendEmail}>");
  assert.match(form[1], /<input[^>]*type="email"/);
  assert.match(form[1], /<button[^>]*type="submit"/);
});

test("#34 the button no longer sends on click as well, which would send twice", () => {
  const button = source.match(/<button[\s\S]*?type="submit"[\s\S]*?>/)[0];
  assert.doesNotMatch(button, /onClick/);
});

test("#34 the submit handler cancels the browser's own form submission", () => {
  assert.match(source, /const sendEmail = async \(event\) => \{\s*event\.preventDefault\(\);/);
});
