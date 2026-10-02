// Moves the one inline script that changes on every build (the module boot script, whose
// content names the hashed chunks) into /assets/boot-<hash>.js, so the page keeps only three
// inline scripts whose content never changes and the CSP can allow them by constant hash.
// Fails the build when the React Router shell is not the one the CSP expects.
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, realpathSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const sha = (text) => "sha256-" + createHash("sha256").update(text).digest("base64");

// html -> { html, boot: { name, body } }; throws when the shell is not what the CSP expects.
export function externalizeBoot(html, allowedHashes) {
  const boot = /<script type="module" async="">([\s\S]*?)<\/script>/.exec(html);
  if (!boot) throw new Error("boot script not found: the React Router shell changed");
  const name = `boot-${createHash("sha256").update(boot[1]).digest("hex").slice(0, 8)}.js`;
  const out = html
    // No `async`: a module script with a src is deferred, so it runs after the inline scripts that
    // follow it feed the router its data. With `async` it could run first and React reported a
    // hydration mismatch (#418) on every page load.
    .replace(boot[0], `<script type="module" src="/assets/${name}"></script>`)
    .replace("</head>", `<link rel="modulepreload" href="/assets/${name}"/></head>`);
  const inline = [...out.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => sha(m[1]));
  const unexpected = inline.filter((hash) => !allowedHashes.includes(hash));
  if (unexpected.length) throw new Error(`inline scripts not covered by the CSP: ${unexpected.join(", ")}`);
  if (/<style[\s>]|\sstyle=/.test(out)) throw new Error("inline style found: the CSP forbids it");
  return { html: out, boot: { name, body: boot[1] } };
}

// Every page the build wrote must end up with no inline module script and only allowed inline scripts.
export function verifyBuild(dir, allowedHashes) {
  const pages = readdirSync(dir).filter((file) => file.endsWith(".html"));
  if (!pages.length) throw new Error(`no html page found in ${dir}`);
  for (const page of pages) {
    const html = readFileSync(new URL(page, dir), "utf8");
    if (/<script[^>]*type="module"(?![^>]*\ssrc=)[^>]*>/.test(html)) throw new Error(`${page}: inline module script left`);
    const unexpected = [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)]
      .map((m) => sha(m[1])).filter((hash) => !allowedHashes.includes(hash));
    if (unexpected.length) throw new Error(`${page}: inline scripts not covered by the CSP: ${unexpected.join(", ")}`);
  }
}

function run() {
  const dir = new URL("../build/client/", import.meta.url);
  const allowed = JSON.parse(readFileSync(new URL("../csp-hashes.json", import.meta.url), "utf8"));
  const { html, boot } = externalizeBoot(readFileSync(new URL("index.html", dir), "utf8"), allowed);
  writeFileSync(new URL(`assets/${boot.name}`, dir), boot.body);
  writeFileSync(new URL("index.html", dir), html);
  verifyBuild(dir, allowed);
}

// import.meta.url is percent-encoded and argv[1] may be a symlink: compare real file paths.
if (process.argv[1] && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url))) run();
