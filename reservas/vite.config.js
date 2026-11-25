import { reactRouter } from "@react-router/dev/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [reactRouter()],
  server: {
    host: "0.0.0.0",
    allowedHosts: [process.env.E2E_HOST || "reservas-e2e"],
  },
  // Keep the build-time SPA prerender reachable in Node versions that resolve
  // localhost to IPv6 before the preview server's IPv4 listener.
  preview: { host: "127.0.0.1" },
});
