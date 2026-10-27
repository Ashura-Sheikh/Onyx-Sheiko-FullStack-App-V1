// Which panels are shown, and whether the side area is open, remembered in
// this browser. Layout preferences only: panel ids and a yes/no, nothing
// from the vault (issue #7). Panel sizes are saved by react-resizable-panels
// under its own keys, also sizes only.

export const LAYOUT_KEY = 'onyx-layout'

export type LayoutPrefs = { visible: string[]; sideOpen: boolean }

export function loadLayout(
  knownIds: string[],
  defaults: string[],
  storage: Storage | undefined = globalThis.localStorage,
): LayoutPrefs {
  try {
    const raw = storage?.getItem(LAYOUT_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : null
    if (parsed && typeof parsed === 'object') {
      const { visible, sideOpen } = parsed as Record<string, unknown>
      if (Array.isArray(visible) && typeof sideOpen === 'boolean') {
        // Only ids of panels that still exist, each once, in registry order.
        const wanted = new Set(visible.filter((v): v is string => typeof v === 'string'))
        return { visible: knownIds.filter((id) => wanted.has(id)), sideOpen }
      }
    }
  } catch {
    // unreadable or blocked: fall back to the defaults
  }
  return { visible: defaults, sideOpen: true }
}

export function saveLayout(prefs: LayoutPrefs, storage: Storage | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(LAYOUT_KEY, JSON.stringify(prefs))
  } catch {
    // storage blocked: the layout still changes for this visit
  }
}
