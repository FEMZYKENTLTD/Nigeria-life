import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the API runs on :8000; the dashboard always calls relative /api URLs.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { host: "0.0.0.0", port: 5173, allowedHosts: true, proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist", chunkSizeWarningLimit: 900 },
});
