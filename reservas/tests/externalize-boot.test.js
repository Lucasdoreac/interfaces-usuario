import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { externalizeBoot } from "../scripts/externalize-boot.mjs";

// The three constant inline scripts and the per-build boot script, copied from the index.html that
// `react-router build` produced for this app. If a React Router update changes them, the build
// fails (scripts/externalize-boot.mjs); update csp-hashes.json and these literals together.
const CONTEXT = "window.__reactRouterContext = {\"basename\":\"/\",\"future\":{\"unstable_enableNodeReadableStream\":false,\"unstable_optimizeDeps\":false},\"routeDiscovery\":{\"mode\":\"initial\"},\"ssr\":false,\"isSpaMode\":true};window.__reactRouterContext.stream = new ReadableStream({start(controller){window.__reactRouterContext.streamController = controller;}}).pipeThrough(new TextEncoderStream());";
const BOOT = (hash) => "import \"/assets/manifest-" + hash + ".js\";\nimport * as route0 from \"/assets/root-" + hash + ".js\";\n  \n  window.__reactRouterRouteModules = {\"root\":route0};\n\nimport(\"/assets/entry.client-" + hash + ".js\");";
const ENQUEUE = "window.__reactRouterContext.streamController.enqueue(\"[{\\\"_1\\\":2,\\\"_3\\\":-5,\\\"_4\\\":-5},\\\"loaderData\\\",{},\\\"actionData\\\",\\\"errors\\\"]\\n\");";
const CLOSE = "window.__reactRouterContext.streamController.close();";
const shell = (hash) =>
  `<!DOCTYPE html><html><head></head><body><script>${CONTEXT}</script><script type="module" async="">${BOOT(hash)}</script><!--$--><script>${ENQUEUE}</script><!--$--><script>${CLOSE}</script></body></html>`;

const sha = (text) => "sha256-" + createHash("sha256").update(text).digest("base64");
const ALLOWED = JSON.parse(readFileSync(new URL("../csp-hashes.json", import.meta.url), "utf8"));
const inline = (html) => [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => sha(m[1]));

test("csp-hashes.json holds exactly the hashes of the three constant inline scripts", () => {
  assert.deepEqual([CONTEXT, ENQUEUE, CLOSE].map(sha), ALLOWED);
});

test("the build-specific module script moves to a file; the page keeps three constant inline scripts", () => {
  const first = externalizeBoot(shell("aaaa1111"), ALLOWED);
  const second = externalizeBoot(shell("bbbb2222"), ALLOWED);
  assert.match(first.html, /<script type="module" src="\/assets\/boot-[0-9a-f]{8}\.js"><\/script>/);
  assert.doesNotMatch(first.html, /<script type="module" async/, "async would let the boot run before the data scripts");
  assert.match(first.html, /<link rel="modulepreload" href="\/assets\/boot-[0-9a-f]{8}\.js"\/><\/head>/);
  assert.equal(first.boot.body, BOOT("aaaa1111"));
  assert.notEqual(first.boot.name, second.boot.name); // the file name carries the build
  assert.deepEqual(inline(first.html), inline(second.html)); // ...but the inline part never changes
  assert.deepEqual(inline(first.html), ALLOWED);
});

test("a changed shell fails the build instead of shipping a page the CSP would blank", () => {
  assert.throws(() => externalizeBoot(shell("aaaa1111").replace("</body>", "<script>alert(1)</script></body>"), ALLOWED), /not covered by the CSP/);
  assert.throws(() => externalizeBoot(shell("aaaa1111").replace("</head>", "<style>a{}</style></head>"), ALLOWED), /inline style/);
  assert.throws(() => externalizeBoot(shell("aaaa1111").replace("window.__reactRouterContext", "window.__changed"), ALLOWED), /not covered by the CSP/);
  assert.throws(() => externalizeBoot("<html></html>", ALLOWED), /shell changed/);
});

// The CLI guard once compared import.meta.url (percent-encoded) with argv[1], so with a space or a
// symlink in the path the postbuild did nothing and exited 0, leaving the inline boot script.
function project(parent) {
  const root = join(mkdtempSync(join(tmpdir(), "boot ")), parent);
  mkdirSync(join(root, "scripts"), { recursive: true });
  mkdirSync(join(root, "build/client/assets"), { recursive: true });
  copyFileSync(new URL("../scripts/externalize-boot.mjs", import.meta.url), join(root, "scripts/externalize-boot.mjs"));
  copyFileSync(new URL("../csp-hashes.json", import.meta.url), join(root, "csp-hashes.json"));
  return root;
}
const run = (script) => spawnSync(process.execPath, [script], { encoding: "utf8" });
const bootFiles = (root) => readdirSync(join(root, "build/client/assets")).filter((f) => f.startsWith("boot-"));

test("the CLI externalizes the boot script even with a space in the path", () => {
  const root = project("my app");
  writeFileSync(join(root, "build/client/index.html"), shell("aaaa1111"));
  const result = run(join(root, "scripts/externalize-boot.mjs"));
  assert.equal(result.status, 0, result.stderr);
  assert.equal(bootFiles(root).length, 1);
  assert.match(readFileSync(join(root, "build/client/index.html"), "utf8"), /src="\/assets\/boot-[0-9a-f]{8}\.js"/);
});

test("the CLI also runs when started through a symlink", () => {
  const root = project("real");
  writeFileSync(join(root, "build/client/index.html"), shell("aaaa1111"));
  const link = join(root, "..", "link.mjs");
  symlinkSync(join(root, "scripts/externalize-boot.mjs"), link);
  const result = run(link);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(bootFiles(root).length, 1);
});

test("the CLI exits non-zero when the shell was altered, and leaves nothing half-done", () => {
  const root = project("altered");
  writeFileSync(join(root, "build/client/index.html"), shell("aaaa1111").replace("</body>", "<script>alert(1)</script></body>"));
  const result = run(join(root, "scripts/externalize-boot.mjs"));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /not covered by the CSP/);
});

test("the CLI fails when another page of the build still carries an inline module script", () => {
  const root = project("second");
  writeFileSync(join(root, "build/client/index.html"), shell("aaaa1111"));
  writeFileSync(join(root, "build/client/other.html"), shell("bbbb2222"));
  const result = run(join(root, "scripts/externalize-boot.mjs"));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /other\.html: inline module script left/);
});
