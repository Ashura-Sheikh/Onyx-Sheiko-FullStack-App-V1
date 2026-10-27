import { describe, expect, it } from 'vitest'
import type { NoteSummary } from './api'
import { buildTree, filterNotes, tagCounts } from './notesTree'

const note = (path: string, tags: string[] = [], updated = '2031-04-01T00:00:00+00:00'): NoteSummary => {
  const slash = path.lastIndexOf('/')
  return { path, title: path.slice(slash + 1, -3), folder: slash === -1 ? '' : path.slice(0, slash), updated, tags }
}

describe('notes tree', () => {
  it('builds nested folders, sorted by name ignoring case', () => {
    const tree = buildTree([note('b/x.md'), note('A/y.md'), note('A/deep/z.md'), note('top.md')])
    expect(tree.folders.map((f) => f.name)).toEqual(['A', 'b'])
    expect(tree.folders[0].folders.map((f) => f.path)).toEqual(['A/deep'])
    expect(tree.notes.map((n) => n.title)).toEqual(['top'])
  })

  it('a folder shows its own and its subfolders\' notes, not a folder with a longer name', () => {
    const notes = [note('Projects/a.md'), note('Projects/Old/b.md'), note('ProjectsOld/c.md')]
    expect(filterNotes(notes, { folder: 'Projects' }).map((n) => n.path)).toEqual(['Projects/a.md', 'Projects/Old/b.md'])
  })

  it('newest first, compared as times even with different offsets', () => {
    const notes = [note('a.md', [], '2031-04-01T10:00:00+00:00'), note('b.md', [], '2031-04-01T11:30:00+02:00')]
    // b is 09:30 UTC, so a (10:00 UTC) is newer, though "11:30" sorts after "10:00" as text.
    expect(filterNotes(notes, {}).map((n) => n.path)).toEqual(['a.md', 'b.md'])
  })

  it('counts each tag once per note, most used first', () => {
    const notes = [note('a.md', ['x', 'x', 'y']), note('b.md', ['y'])]
    expect(tagCounts(notes)).toEqual([
      { tag: 'y', count: 2 },
      { tag: 'x', count: 1 },
    ])
  })
})
