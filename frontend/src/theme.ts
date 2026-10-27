// Light and dark mode. Starts from the system setting; the toggle remembers
// the choice in this browser. Only the word "light" or "dark" is stored:
// a layout preference, nothing sensitive (issue #7).

export type Theme = 'light' | 'dark'

export const THEME_KEY = 'onyx-theme'

function stored(storage: Storage | undefined): Theme | null {
  try {
    const value = storage?.getItem(THEME_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null // storage blocked
  }
}

export function initialTheme(
  storage: Storage | undefined = globalThis.localStorage,
  prefersDark: boolean = globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false,
): Theme {
  return stored(storage) ?? (prefersDark ? 'dark' : 'light')
}

/** Show the theme. A class on <html>, never an inline style (CSP). */
export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  root.classList.toggle('dark', theme === 'dark')
}

export function saveTheme(theme: Theme, storage: Storage | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(THEME_KEY, theme)
  } catch {
    // storage blocked: the theme still changes for this visit
  }
}
