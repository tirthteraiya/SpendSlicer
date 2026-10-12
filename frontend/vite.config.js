import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendUrl = process.env.VITE_BACKEND_URL || "http://127.0.0.1:8080";

export default defineConfig({
  base: "/app/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backendUrl,
    },
  },
  build: {
    // Build straight into the Python package so one path serves the bundle in
    // a source checkout, an installed wheel, and a frozen desktop build.
    outDir: "../spendslicer/web/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Function form: the object form left React inside the recharts chunk
        // (the "react" chunk was an empty re-export), so React re-downloaded
        // with every charting upgrade.
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return "react";
          return "vendor";
        },
      },
    },
  },
});
