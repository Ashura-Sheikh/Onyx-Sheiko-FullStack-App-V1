/** True for ⌘K on a Mac and Ctrl+K elsewhere. */
export function isPaletteShortcut(event: { key: string; metaKey: boolean; ctrlKey: boolean }): boolean {
  return (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k'
}
