import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

// The Auth e-mail loads this file through EMAIL_ASSETS_URL=<web>/labtech/email-icones.
const logo = readFileSync(new URL("../public/labtech/email-icones/dw-corp-logo.png", import.meta.url));

test("the e-mail logo is a real PNG served from public/", () => {
  assert.equal(logo.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
});

test("the e-mail logo is at least 2x the 192 px it is displayed at, with transparency", () => {
  const width = logo.readUInt32BE(16);
  const height = logo.readUInt32BE(20);
  const colorType = logo[25];
  assert.ok(width >= 384, `width ${width} is too small for a sharp 192 px display`);
  assert.ok(height > 0 && width / height > 3, "unexpected aspect ratio for the wordmark with its tagline");
  assert.equal(colorType, 6, "PNG must be RGBA so it sits on the e-mail card without a box");
});

test("the e-mail logo stays small enough for e-mail clients", () => {
  assert.ok(logo.length < 60 * 1024, `${logo.length} bytes`);
});
