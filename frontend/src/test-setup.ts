import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// Vitest globals are off, so Testing Library can't clean up on its own.
afterEach(cleanup)

// jsdom has no ResizeObserver; react-resizable-panels needs one. Every real
// browser has it. This stand-in never reports sizes, which is all jsdom can do.
class ResizeObserverStandIn {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStandIn as unknown as typeof ResizeObserver
