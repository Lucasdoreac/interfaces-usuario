// Moves the one inline script that changes on every build (the module boot script, whose
// content names the hashed chunks) into /assets/boot-<hash>.js, so the page keeps only three
// inline scripts whose content never changes and the CSP can allow them by constant hash.
// Fails the build when the React Router shell is not the one the CSP expects.
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const sha = (text) => "sha256-" + createHash("sha256").update(text).digest("base64");

// Script tags the way the HTML parser reads them: any letter case, attributes in any order and
// quoted or not. Attribute names are parsed, so a "src=" inside another attribute's value does
// not count as a src. An inline script is one without a src attribute.
const SCRIPT = /<script(?=[\s/>])((?:"[^"]*"|'[^']*'|[^>"'])*)>([\s\S]*?)<\/script\s*>/gi;
const ATTR = /([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
const attributes = (text) =>
  new Map([...text.matchAll(ATTR)].map((m) => [m[1].toLowerCase(), (m[2] ?? m[3] ?? m[4] ?? "").trim()]));
const inlineScripts = (html) =>
  [...html.matchAll(SCRIPT)].map((m) => ({ attrs: attributes(m[1]), body: m[2] })).filter((s) => !s.attrs.has("src"));
const isModule = (script) => script.attrs.get("type")?.toLowerCase() === "module";

// html -> { html, boot: { name, body } }; throws when the shell is not what the CSP expects.
export function externalizeBoot(html, allowedHashes) {
  const boot = /<script type="module" async="">([\s\S]*?)<\/script>/.exec(html);
  if (!boot) throw new Error("boot script not found: the React Router shell changed");
  const name = `boot-${createHash("sha256").update(boot[1]).digest("hex").slice(0, 16)}.js`;
  const out = html
    // No `async`: a module script with a src is deferred, so it runs after the inline scripts that
    // follow it feed the router its data. With `async` it could run first and React reported a
    // hydration mismatch (#418) on every page load.
    .replace(boot[0], `<script type="module" src="/assets/${name}"></script>`)
    .replace("</head>", `<link rel="modulepreload" href="/assets/${name}"/></head>`);
  const inline = inlineScripts(out).map((script) => sha(script.body));
  const unexpected = inline.filter((hash) => !allowedHashes.includes(hash));
  if (unexpected.length) throw new Error(`inline scripts not covered by the CSP: ${unexpected.join(", ")}`);
  if (/<style[\s>]|\sstyle=/.test(out)) throw new Error("inline style found: the CSP forbids it");
  return { html: out, boot: { name, body: boot[1] } };
}

// Every page the build wrote must end up with no inline module script and only allowed inline scripts.
export function verifyBuild(dir, allowedHashes) {
  const root = fileURLToPath(dir);
  const pages = htmlFiles(root);
  if (!pages.length) throw new Error(`no html page found in ${root}`);
  for (const page of pages) {
    const name = page.slice(root.length).replace(/^[\\/]+/, "");
    const scripts = inlineScripts(readFileSync(page, "utf8"));
    if (scripts.some(isModule)) throw new Error(`${name}: inline module script left`);
    const unexpected = scripts.map((script) => sha(script.body)).filter((hash) => !allowedHashes.includes(hash));
    if (unexpected.length) throw new Error(`${name}: inline scripts not covered by the CSP: ${unexpected.join(", ")}`);
  }
}

// Every .html under dir, in subfolders too, in any letter case of the extension.
function htmlFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return htmlFiles(path);
    return /\.html?$/i.test(entry.name) ? [path] : [];
  });
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
