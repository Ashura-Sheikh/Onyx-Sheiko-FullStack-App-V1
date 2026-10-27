// Which panels are shown, and whether the side area is open, remembered in
// this browser. Layout preferences only: panel ids and a yes/no, nothing
// from the vault (issue #7). Panel sizes are saved by react-resizable-panels
// under its own keys, also sizes only.
//
// `seen` lists every panel this browser has been offered. A panel added to
// the app later (with defaultVisible) shows up once by default; after that
// the user's choice wins, including removing it.

export const LAYOUT_KEY = 'onyx-layout'

export type LayoutPrefs = { visible: string[]; sideOpen: boolean; seen: string[] }

// Layouts saved before `seen` existed (#7 part 3) had exactly these panels.
const SEEN_BEFORE_TRACKING = ['details', 'history']

export function loadLayout(
  knownIds: string[],
  defaults: string[],
  storage: Storage | undefined = globalThis.localStorage,
): LayoutPrefs {
  try {
    const raw = storage?.getItem(LAYOUT_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : null
    if (parsed && typeof parsed === 'object') {
      const { visible, sideOpen, seen } = parsed as Record<string, unknown>
      if (Array.isArray(visible) && typeof sideOpen === 'boolean') {
        const strings = (list: unknown[]) => new Set(list.filter((v): v is string => typeof v === 'string'))
        const wanted = strings(visible)
        const offered = Array.isArray(seen) ? strings(seen) : new Set(SEEN_BEFORE_TRACKING)
        // Panels new to this browser that should show by default.
        for (const id of defaults) if (!offered.has(id)) wanted.add(id)
        // Only ids of panels that still exist, each once, in registry order.
        return { visible: knownIds.filter((id) => wanted.has(id)), sideOpen, seen: knownIds }
      }
    }
  } catch {
    // unreadable or blocked: fall back to the defaults
  }
  return { visible: defaults, sideOpen: true, seen: knownIds }
}

export function saveLayout(prefs: LayoutPrefs, storage: Storage | undefined = globalThis.localStorage): void {
  try {
    storage?.setItem(LAYOUT_KEY, JSON.stringify(prefs))
  } catch {
    // storage blocked: the layout still changes for this visit
  }
}
