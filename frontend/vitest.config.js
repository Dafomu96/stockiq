import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    // jsdom simulates a browser environment so localStorage, DOM APIs,
    // and React rendering work without a real browser
    environment: 'jsdom',

    // Run setup file before each test file — imports @testing-library/jest-dom
    // matchers (toBeInTheDocument, toHaveTextContent, etc.)
    setupFiles: ['./src/__tests__/setup.js'],

    // Include all test files under src/__tests__/
    include: ['src/__tests__/**/*.test.{js,jsx}'],

    // Coverage via V8 (fastest, no instrumentation needed)
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/main.jsx', 'src/__tests__/**'],
      thresholds: {
        lines:      70,
        functions:  70,
        branches:   65,
        statements: 70,
      },
    },

    globals: true,   // describe/it/expect available without imports
  },
})
