/**
 * Global test setup — runs before every test file.
 *
 * 1. Imports @testing-library/jest-dom to add DOM matchers:
 *    toBeInTheDocument, toHaveTextContent, toBeDisabled, etc.
 *
 * 2. Stubs localStorage — jsdom has localStorage but it persists between
 *    tests in the same file. We clear it before each test to prevent
 *    cross-test pollution.
 *
 * 3. Stubs crypto.randomUUID — not available in jsdom by default.
 */

import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Clear localStorage before every test
beforeEach(() => {
  localStorage.clear()
})

// Stub crypto.randomUUID — jsdom doesn't implement it
if (typeof crypto.randomUUID !== 'function') {
  let counter = 0
  vi.stubGlobal('crypto', {
    ...crypto,
    randomUUID: () => `test-uuid-${++counter}`,
  })
}
