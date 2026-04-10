import { defineConfig } from "vitest/config"

export default defineConfig({
  test: {
    include: ["e2e/**/*.test.ts"],
    exclude: ["node_modules/**", "tmp/**"],
    timeout: 120000,
    hookTimeout: 120000,
  },
})