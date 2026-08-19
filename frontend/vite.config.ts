import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
    // In Docker Compose, the browser hitting this dev server might be on the
    // host (http://localhost:5173) or inside another container on the same
    // network (e.g. the `e2e` service, via http://frontend:5173) — either
    // way "localhost:8000" from that browser's perspective is wrong. Proxying
    // /api server-side (where the "backend" Docker hostname always resolves)
    // means the browser only ever needs a same-origin relative path,
    // regardless of where it's running. Only active when VITE_PROXY_TARGET is
    // set (i.e. in docker-compose); plain `npm run dev` outside Docker is
    // unaffected and keeps using the absolute VITE_API_BASE_URL default.
    proxy: process.env.VITE_PROXY_TARGET
      ? {
          "/api": {
            target: process.env.VITE_PROXY_TARGET,
            changeOrigin: true,
          },
        }
      : undefined,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    // Pin the API base URL the test suite sees, regardless of whatever
    // VITE_API_BASE_URL happens to be set to in the invoking shell (e.g. the
    // relative "/api/v1" docker-compose sets for the frontend *dev server* —
    // irrelevant here since tests run in Node/jsdom, not through Vite's dev
    // proxy, and MSW's mocks in src/test/server.ts are written against this
    // exact absolute URL).
    env: {
      VITE_API_BASE_URL: "http://localhost:8000/api/v1",
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      reportsDirectory: "./reports/coverage",
    },
    reporters: ["default", "junit"],
    outputFile: {
      junit: "./reports/junit.xml",
    },
  },
});
