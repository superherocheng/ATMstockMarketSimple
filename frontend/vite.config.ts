import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// Dev: same-origin proxy → backend on :5656. Avoids CORS for ALL GET reads
// (the CSRF guard only intercepts POST). POST write-ops still need the
// Bearer API_TOKEN — handled in Agent 2/4.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:5656", changeOrigin: true },
      "/health": { target: "http://localhost:5656", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    // Deployment: copy dist/* into FastAPI static dir (Agent 2 wires the route).
  },
});
