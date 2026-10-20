import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const configUrl = pathToFileURL(resolve(projectRoot, "vite.config.js")).href;

async function loadConfig(env) {
  const saved = { ALLOWED_HOSTS: process.env.ALLOWED_HOSTS, E2E_HOST: process.env.E2E_HOST };
  for (const key of Object.keys(saved)) delete process.env[key];
  Object.assign(process.env, env);
  try {
    return (await import(`${configUrl}?${Math.random()}`)).default;
  } finally {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  }
}

function listFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? listFiles(join(dir, entry.name)) : [join(dir, entry.name)],
  );
}

test("envPrefix accepts VITE_ and REACT_APP_ variables", async () => {
  const config = await loadConfig({});
  assert.deepEqual([...config.envPrefix].sort(), ["REACT_APP_", "VITE_"]);
});

test("dev server host, port and allowedHosts follow the CRA behaviour", async () => {
  const open = await loadConfig({});
  assert.equal(open.server.host, "0.0.0.0");
  assert.equal(open.server.port, 3000);
  assert.equal(open.server.allowedHosts, true);
  assert.equal(open.preview.allowedHosts, true);

  const restricted = await loadConfig({ ALLOWED_HOSTS: "a.example, b.example" });
  assert.deepEqual(restricted.server.allowedHosts, ["a.example", "b.example"]);

  const e2e = await loadConfig({ E2E_HOST: "reservas-e2e" });
  assert.deepEqual(e2e.server.allowedHosts, ["reservas-e2e"]);
});

test("build writes index.html and assets at the build root and embeds REACT_APP_API_BASE_URL", {
  timeout: 240_000,
}, () => {
  // Dentro do projeto: o prerender da SPA exige um buildDirectory sob a raiz.
  const buildDir = mkdtempSync(join(projectRoot, ".tmp-build-"));
  const outDir = basename(buildDir);
  const url = "https://api-contract.example.test";
  const env = { ...process.env, BUILD_DIR: outDir, REACT_APP_API_BASE_URL: url };
  delete env.VITE_API_BASE_URL;
  try {
    for (const args of [
      ["node_modules/@react-router/dev/bin.cjs", "build"],
      ["scripts/flatten-build.mjs", outDir],
    ]) {
      const result = spawnSync(process.execPath, args, { cwd: projectRoot, env, encoding: "utf8" });
      assert.equal(result.status, 0, `${args.join(" ")}\n${result.stdout}\n${result.stderr}`);
    }
    assert.ok(existsSync(join(buildDir, "index.html")), "build/index.html must exist");
    assert.ok(existsSync(join(buildDir, "assets")), "assets must live in the build root");
    assert.ok(!existsSync(join(buildDir, "client")), "build/client must be flattened");
    assert.ok(!existsSync(join(buildDir, "server")), "build/server must not be shipped");
    const embedded = listFiles(join(buildDir, "assets"))
      .filter((file) => file.endsWith(".js"))
      .some((file) => readFileSync(file, "utf8").includes(url));
    assert.ok(embedded, "REACT_APP_API_BASE_URL should be embedded in the client bundle");
  } finally {
    rmSync(buildDir, { recursive: true, force: true });
  }
});
