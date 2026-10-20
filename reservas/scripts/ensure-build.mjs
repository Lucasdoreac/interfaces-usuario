// pretest: gera a SPA (yarn build) somente se `build/index.html` ainda não existir.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
if (existsSync(join(projectRoot, "build", "index.html"))) process.exit(0);

console.log("build/index.html ausente; executando yarn build antes dos testes.");
const yarn = process.platform === "win32" ? "yarn.cmd" : "yarn";
const result = spawnSync(yarn, ["build"], { cwd: projectRoot, stdio: "inherit" });
process.exit(result.status ?? 1);
