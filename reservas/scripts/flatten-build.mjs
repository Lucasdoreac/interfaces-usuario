// Entrega a SPA no layout do CRA: `build/index.html` e assets na raiz de `build/`.
// O React Router grava a SPA em `<buildDirectory>/client`; em modo SPA (ssr:false)
// o bundle de servidor não é usado em runtime e não é publicado.
import { cpSync, existsSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const buildDir = resolve(projectRoot, process.argv[2] || process.env.BUILD_DIR || "build");
const clientDir = join(buildDir, "client");

if (!existsSync(join(clientDir, "index.html"))) {
  if (existsSync(join(buildDir, "index.html"))) process.exit(0);
  console.error(`SPA não encontrada em ${clientDir}; execute react-router build antes.`);
  process.exit(1);
}

cpSync(clientDir, buildDir, { recursive: true, force: true });
rmSync(clientDir, { recursive: true, force: true });
rmSync(join(buildDir, "server"), { recursive: true, force: true });
