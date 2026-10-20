import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

// Sem restrição por padrão (como o CRA). ALLOWED_HOSTS (lista separada por vírgula)
// ou E2E_HOST restringem o dev/preview aos hosts informados.
const restricted = [process.env.ALLOWED_HOSTS, process.env.E2E_HOST]
  .flatMap((value) => (value || "").split(","))
  .map((host) => host.trim())
  .filter(Boolean);
const allowedHosts = restricted.length ? restricted : true;

// Depois do pós-build a SPA fica em `build/` (não em `build/client`); a prévia a serve de lá.
const outDir = process.env.BUILD_DIR || "build";
const servePreviewFromBuildRoot = {
  name: "preview-from-build-root",
  config: (_config, { isPreview }) =>
    isPreview ? { build: { outDir }, environments: { client: { build: { outDir } } } } : {},
};

export default defineConfig({
  plugins: [reactRouter(), servePreviewFromBuildRoot],
  // Aceita VITE_* e as REACT_APP_* herdadas do CRA.
  envPrefix: ["VITE_", "REACT_APP_"],
  server: { host: "0.0.0.0", port: 3000, allowedHosts },
  // Keep the build-time SPA prerender reachable in Node versions that resolve
  // localhost to IPv6 before the preview server's IPv4 listener.
  preview: { host: "127.0.0.1", allowedHosts },
});
