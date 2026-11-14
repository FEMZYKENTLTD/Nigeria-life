import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to the FastAPI backend. In production the built
// bundle is served by the backend itself (single origin, no CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    // The sandbox proxies the preview through an arbitrary e2b.app host —
    // allow all hosts in dev (production serving is done by the backend).
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8787", changeOrigin: true },
      "/data": { target: "http://127.0.0.1:8787", changeOrigin: true },
    },
  },
});
