import type { NoteSummary } from './api'

export type Folder = { path: string; name: string; folders: Folder[]; notes: NoteSummary[] }

/** Builds the folder tree from the flat note list. Folders and notes sorted by name, ignoring case. */
export function buildTree(notes: NoteSummary[]): Folder {
  const root: Folder = { path: '', name: 'Vault', folders: [], notes: [] }
  const byPath = new Map<string, Folder>([['', root]])
  const folderFor = (path: string): Folder => {
    const existing = byPath.get(path)
    if (existing) return existing
    const slash = path.lastIndexOf('/')
    const parent = folderFor(slash === -1 ? '' : path.slice(0, slash))
    const folder: Folder = { path, name: path.slice(slash + 1), folders: [], notes: [] }
    parent.folders.push(folder)
    byPath.set(path, folder)
    return folder
  }
  for (const note of notes) folderFor(note.folder).notes.push(note)
  const byName = (a: { name?: string; title?: string }, b: { name?: string; title?: string }) =>
    (a.name ?? a.title ?? '').localeCompare(b.name ?? b.title ?? '', undefined, { sensitivity: 'base' })
  const sort = (folder: Folder) => {
    folder.folders.sort(byName)
    folder.notes.sort(byName)
    folder.folders.forEach(sort)
  }
  sort(root)
  return root
}

/** Every tag with the number of notes that have it, most used first, then by name. */
export function tagCounts(notes: NoteSummary[]): { tag: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const note of notes) for (const tag of new Set(note.tags)) counts.set(tag, (counts.get(tag) ?? 0) + 1)
  return [...counts]
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
}

/** Notes in a folder (including its subfolders), or with a tag; newest first. */
export function filterNotes(notes: NoteSummary[], filter: { folder?: string; tag?: string }): NoteSummary[] {
  const shown = notes.filter((n) => {
    if (filter.tag !== undefined) return n.tags.includes(filter.tag)
    if (filter.folder) return n.folder === filter.folder || n.folder.startsWith(`${filter.folder}/`)
    return true
  })
  // Compared as times, not text: two notes can record different time-zone offsets.
  return shown.sort((a, b) => Date.parse(b.updated) - Date.parse(a.updated) || a.path.localeCompare(b.path))
}
