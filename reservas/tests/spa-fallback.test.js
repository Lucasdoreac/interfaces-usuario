import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { after, before, test } from "node:test";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const viteCli = resolve(projectRoot, "node_modules/vite/bin/vite.js");
let preview;
let previewUrl;
let previewOutput = "";

async function findAvailablePort() {
  const probe = createServer();
  await new Promise((resolveListen, reject) => {
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", resolveListen);
  });
  const { port } = probe.address();
  await new Promise((resolveClose, reject) =>
    probe.close((error) => (error ? reject(error) : resolveClose())),
  );
  return port;
}

before(async () => {
  const port = await findAvailablePort();
  previewUrl = `http://127.0.0.1:${port}`;
  preview = spawn(
    process.execPath,
    [viteCli, "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
    { cwd: projectRoot, stdio: ["ignore", "pipe", "pipe"] },
  );
  preview.stdout.setEncoding("utf8").on("data", (chunk) => (previewOutput += chunk));
  preview.stderr.setEncoding("utf8").on("data", (chunk) => (previewOutput += chunk));

  // Build output and Vite startup can contend with the other test files in
  // Docker; allow slower Linux runners to finish initializing the preview.
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (preview.exitCode !== null) {
      throw new Error(`Vite preview exited early.\n${previewOutput}`);
    }
    try {
      const response = await fetch(previewUrl, { signal: AbortSignal.timeout(500) });
      if (response.ok) return;
    } catch {
      // The preview server is still starting.
    }
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
  }
  preview.kill("SIGTERM");
  throw new Error(`Vite preview did not start within 30 seconds.\n${previewOutput}`);
});

after(() => {
  if (preview && preview.exitCode === null) preview.kill("SIGTERM");
});

test("serves the SPA shell for the root and a nested reservation route", async () => {
  const [root, nestedRoute] = await Promise.all([
    fetch(`${previewUrl}/`),
    fetch(`${previewUrl}/event/type-selection`),
  ]);

  assert.equal(root.status, 200, "the SPA root should load from the production build");
  assert.equal(
    nestedRoute.status,
    200,
    "a direct request to a nested route should fall back to the SPA shell",
  );
  assert.equal(
    await nestedRoute.text(),
    await root.text(),
    "nested routes should receive the same client entry document as the root",
  );
});
