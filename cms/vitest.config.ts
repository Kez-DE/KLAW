import path from 'path'
import { fileURLToPath } from 'url'
import { defineConfig } from 'vitest/config'

const dirname = path.dirname(fileURLToPath(import.meta.url))
export default defineConfig({
  resolve: {
    alias: {
      '@payload-config': path.resolve(dirname, './payload.config.ts'),
      '@': path.resolve(dirname, './src'),
    },
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.spec.ts'],
    setupFiles: ['./tests/setup.ts'],
    fileParallelism: false, // Payload mở pool Postgres — song song là tranh chấp
    testTimeout: 60_000,
    hookTimeout: 60_000,
  },
})
