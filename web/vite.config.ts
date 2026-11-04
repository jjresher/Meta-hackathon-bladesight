/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vite + Vitest configuration for the BladeSight web UI (issue #13).
export default defineConfig({
  plugins: [react()],
  // `npm run dev` talks to a local API (`uv run poe serve`, port 8000).
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/images": "http://127.0.0.1:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Playwright specs live under tests/ and run with their own runner.
    exclude: ["**/node_modules/**", "**/dist/**", "tests/**"],
  },
});
