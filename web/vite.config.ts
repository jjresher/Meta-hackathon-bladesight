/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Vite + Vitest configuration for the BladeSight web UI (issue #13).
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Playwright specs live under tests/ and run with their own runner.
    exclude: ["**/node_modules/**", "**/dist/**", "tests/**"],
  },
});
