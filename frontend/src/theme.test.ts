import { describe, expect, it } from 'vitest'
import { applyTheme, initialTheme, saveTheme, THEME_KEY } from './theme'

function memoryStorage(initial: Record<string, string> = {}): Storage {
  const data = new Map(Object.entries(initial))
  return {
    get length() {
      return data.size
    },
    clear: () => data.clear(),
    getItem: (key) => data.get(key) ?? null,
    key: (index) => [...data.keys()][index] ?? null,
    removeItem: (key) => void data.delete(key),
    setItem: (key, value) => void data.set(key, value),
  }
}

const blocked = {
  getItem: () => {
    throw new Error('blocked')
  },
  setItem: () => {
    throw new Error('blocked')
  },
} as unknown as Storage

describe('theme', () => {
  it('follows the system setting when nothing is remembered', () => {
    expect(initialTheme(memoryStorage(), true)).toBe('dark')
    expect(initialTheme(memoryStorage(), false)).toBe('light')
  })

  it('a remembered choice wins over the system setting', () => {
    expect(initialTheme(memoryStorage({ [THEME_KEY]: 'light' }), true)).toBe('light')
    expect(initialTheme(memoryStorage({ [THEME_KEY]: 'dark' }), false)).toBe('dark')
  })

  it('ignores anything stored that is not light or dark', () => {
    expect(initialTheme(memoryStorage({ [THEME_KEY]: '<script>' }), false)).toBe('light')
  })

  it('works when storage is blocked', () => {
    expect(initialTheme(blocked, true)).toBe('dark')
    expect(() => saveTheme('dark', blocked)).not.toThrow()
  })

  it('stores only the word', () => {
    const storage = memoryStorage()
    saveTheme('dark', storage)
    expect(storage.length).toBe(1)
    expect(storage.getItem(THEME_KEY)).toBe('dark')
  })

  it('shows the theme with a class, not a style', () => {
    const root = document.createElement('html')
    applyTheme('dark', root)
    expect(root.className).toBe('dark')
    expect(root.getAttribute('style')).toBeNull()
    applyTheme('light', root)
    expect(root.className).toBe('')
  })
})
