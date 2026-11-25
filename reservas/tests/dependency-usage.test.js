import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return sourceFiles(fullPath);
    return /\.(jsx?|tsx?)$/.test(entry.name) ? [fullPath] : [];
  }));
  return files.flat();
}

test("removed HTTP, UI, and test dependencies have no imports or manifest entries", async () => {
  const manifest = JSON.parse(await readFile(path.join(root, "package.json"), "utf8"));
  const files = await sourceFiles(path.join(root, "src"));
  const imports = [];
  const removedDependencies = [
    "axios",
    "react-bootstrap",
    "@testing-library/dom",
    "@testing-library/jest-dom",
    "@testing-library/react",
    "@testing-library/user-event",
  ];

  for (const file of files) {
    const source = await readFile(file, "utf8");
    if (/(?:from\s*|import\s*\(|require\s*\()\s*["'](?:axios|react-bootstrap(?:\/[^"']*)?|@testing-library\/[^"']+)["']/.test(source)) {
      imports.push(path.relative(root, file));
    }
  }

  assert.deepEqual(imports, [], `removed package imports remain in: ${imports.join(", ")}`);
  for (const packageName of removedDependencies) {
    assert.equal(manifest.dependencies[packageName], undefined, `${packageName} remains in dependencies`);
    assert.equal(manifest.devDependencies?.[packageName], undefined, `${packageName} remains in devDependencies`);
  }
  assert.equal(manifest.resolutions?.["@babel/runtime"], undefined);
});
