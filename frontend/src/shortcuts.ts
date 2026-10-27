/** True for ⌘K on a Mac and Ctrl+K elsewhere. */
export function isPaletteShortcut(event: { key: string; metaKey: boolean; ctrlKey: boolean }): boolean {
  return (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k'
}

/** Shortcut labels say ⌘ on Apple devices, Ctrl elsewhere. */
export const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
