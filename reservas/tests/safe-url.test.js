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
  // the validated URL goes only into href; the text shown to the person is what was stored
  assert.match(source, /href=\{subscriptionUrl\}[\s\S]*?>\s*\{item\.subscriptionLink\}/);
});
