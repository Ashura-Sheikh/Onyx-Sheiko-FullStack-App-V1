import { describe, expect, it } from 'vitest'
import { LAYOUT_KEY, loadLayout, saveLayout } from './layout'

function storageWith(value: string | null): Storage {
  const data = new Map<string, string>()
  if (value !== null) data.set(LAYOUT_KEY, value)
  return {
    get length() {
      return data.size
    },
    clear: () => data.clear(),
    getItem: (k) => data.get(k) ?? null,
    key: (i) => [...data.keys()][i] ?? null,
    removeItem: (k) => void data.delete(k),
    setItem: (k, v) => void data.set(k, v),
  }
}

const KNOWN = ['details', 'history']

describe('layout preferences', () => {
  it('uses the defaults the first time', () => {
    expect(loadLayout(KNOWN, ['details'], storageWith(null))).toEqual({ visible: ['details'], sideOpen: true, seen: KNOWN })
  })

  it('keeps only panels that still exist, once each, in registry order', () => {
    const saved = JSON.stringify({ visible: ['history', 'gone', 'details', 'history', 5], sideOpen: false, seen: KNOWN })
    expect(loadLayout(KNOWN, [], storageWith(saved))).toEqual({ visible: ['details', 'history'], sideOpen: false, seen: KNOWN })
  })

  it.each(['not json', '[]', '{"visible":"details","sideOpen":true}', '{"visible":[],"sideOpen":"yes"}'])(
    'falls back to the defaults for %s',
    (raw) => {
      expect(loadLayout(KNOWN, ['details'], storageWith(raw))).toEqual({ visible: ['details'], sideOpen: true, seen: KNOWN })
    },
  )

  it('saves only ids and a yes/no', () => {
    const storage = storageWith(null)
    saveLayout({ visible: ['details'], sideOpen: false, seen: KNOWN }, storage)
    expect(storage.getItem(LAYOUT_KEY)).toBe('{"visible":["details"],"sideOpen":false,"seen":["details","history"]}')
  })
})

describe('panels added to the app later', () => {
  const NOW = ['details', 'backlinks', 'history', 'tags']
  const DEFAULTS = ['details', 'backlinks', 'history']

  it('a new default panel shows up once in a layout saved before it existed', () => {
    const before = JSON.stringify({ visible: ['history'], sideOpen: true }) // part 3: no `seen`
    expect(loadLayout(NOW, DEFAULTS, storageWith(before)).visible).toEqual(['backlinks', 'history'])
  })

  it('after that, removing it is remembered', () => {
    const later = JSON.stringify({ visible: ['history'], sideOpen: true, seen: NOW })
    expect(loadLayout(NOW, DEFAULTS, storageWith(later)).visible).toEqual(['history'])
  })

  it('a new panel that is hidden by default stays hidden', () => {
    const before = JSON.stringify({ visible: ['details'], sideOpen: true, seen: ['details', 'backlinks', 'history'] })
    expect(loadLayout(NOW, DEFAULTS, storageWith(before)).visible).toEqual(['details'])
  })
})
