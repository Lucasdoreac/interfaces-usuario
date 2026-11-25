import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { safeHttpUrl } from "../src/utils/safeUrl.js";

test("only plain http(s) links pass, normalized", () => {
  assert.equal(safeHttpUrl("https://example.test/a.png"), "https://example.test/a.png");
  assert.equal(safeHttpUrl("  http://example.test/x "), "http://example.test/x");
  assert.equal(safeHttpUrl("https://example.test"), "https://example.test/");
});

test("script, data and look-alike schemes are dropped", () => {
  for (const bad of [
    "javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "java\nscript:alert(1)",
    "data:text/html,<script>alert(1)</script>", "data:image/png;base64,AAAA", "vbscript:x", "blob:https://example.test/u",
    "//example.test/x", "/relative/path", "example.test", "https://user:pw@example.test/", "ftp://example.test/",
    "", "   ", null, undefined, 42, {}, ["https://example.test/"],
  ]) {
    assert.equal(safeHttpUrl(bad), null, String(bad));
  }
});

test("My Events renders the event link and logo only through safeHttpUrl", () => {
  const source = readFileSync(new URL("../src/pages/meus-eventos/MyEvents.jsx", import.meta.url), "utf8");
  assert.match(source, /safeHttpUrl\(item\.eventLogo\)/);
  assert.match(source, /safeHttpUrl\(item\.subscriptionLink\)/);
  assert.doesNotMatch(source, /(src|href)=\{item\.(eventLogo|subscriptionLink)\}/);
  // the validated URL goes only into href; the text shown is what was stored, plus the destination host when it differs (linkText)
  assert.match(source, /href=\{subscriptionUrl\}[\s\S]*?>\s*\{linkText\(item\.subscriptionLink, subscriptionUrl\)\}/);
});

test("link text keeps matching hosts as written", async () => {
  const { linkText } = await import("../src/utils/safeUrl.js");
  for (const text of ["https://example.test/inscricao?x=1", "http://EXAMPLE.test", "https://example.test:8443/a", "https://example.test"]) {
    assert.equal(linkText(text, safeHttpUrl(text)), text);
  }
});

test("link text names the destination when the written host differs from it", async () => {
  const { linkText } = await import("../src/utils/safeUrl.js");
  const idn = "https://аpple.com/login"; // Cyrillic "а"
  const href = safeHttpUrl(idn);
  assert.match(new URL(href).hostname, /^xn--/);
  assert.equal(linkText(idn, href), `${idn} (destino: ${new URL(href).hostname})`);
  const fullwidth = "https://example。test/x";
  assert.equal(linkText(fullwidth, safeHttpUrl(fullwidth)), `${fullwidth} (destino: example.test)`);
  const encoded = "https://%65xample.test/x";
  assert.match(linkText(encoded, safeHttpUrl(encoded)), /\(destino: example\.test\)$/);
});

test("MyEvents renders the subscription text through linkText", () => {
  const source = readFileSync(new URL("../src/pages/meus-eventos/MyEvents.jsx", import.meta.url), "utf8");
  assert.match(source, /linkText\(item\.subscriptionLink, subscriptionUrl\)/);
  assert.doesNotMatch(source, /\{item\.subscriptionLink\}/);
});
