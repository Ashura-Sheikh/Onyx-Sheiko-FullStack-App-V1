import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Group, Panel, Separator, useDefaultLayout } from 'react-resizable-panels'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { focusPath, getNotes, notesPath, search, SEARCH_MIN_CHARS, type NoteSummary } from './api'
import { dateTime } from './labels'
import { buildTree, filterNotes, type Folder } from './notesTree'
import Snippet from './Snippet'
import { useDebounced } from './useDebounced'

const SEPARATOR =
  'w-1.5 shrink-0 bg-stone-200 outline-none hover:bg-emerald-500/40 focus-visible:bg-emerald-500/60 dark:bg-stone-800'

function FolderNode({ folder, selected, depth }: { folder: Folder; selected: string | undefined; depth: number }) {
  const [open, setOpen] = useState(depth === 0 || (selected ?? '').startsWith(folder.path))
  const isSelected = selected === folder.path
  return (
    <li>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={`${open ? 'Collapse' : 'Expand'} ${folder.name}`}
          className="w-5 shrink-0 rounded text-stone-500 hover:bg-stone-200 dark:hover:bg-stone-800"
        >
          {open ? '▾' : '▸'}
        </button>
        <Link
          to={notesPath({ folder: folder.path })}
          onClick={() => setOpen(true)}
          aria-current={isSelected ? 'page' : undefined}
          className={`min-w-0 flex-1 truncate rounded px-1.5 py-0.5 ${isSelected ? 'bg-stone-200 font-medium dark:bg-stone-800' : 'hover:bg-stone-200 dark:hover:bg-stone-800'}`}
        >
          {folder.name}
        </Link>
      </div>
      {open && (
        <ul className="ml-4">
          {folder.folders.map((child) => (
            <FolderNode key={child.path} folder={child} selected={selected} depth={depth + 1} />
          ))}
          {folder.notes.map((note) => (
            <li key={note.path}>
              <Link to={focusPath(note.path)} className="block truncate rounded py-0.5 pl-6 text-stone-600 hover:underline dark:text-stone-400">
                {note.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function NoteList({ notes }: { notes: NoteSummary[] }) {
  if (notes.length === 0) return <p className="py-3 text-stone-500">No notes here.</p>
  return (
    <ul className="divide-y divide-stone-200 dark:divide-stone-800">
      {notes.map((note) => (
        <li key={note.path} className="py-2.5">
          <Link to={focusPath(note.path)} className="block truncate font-medium hover:underline">
            {note.title}
          </Link>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500">
            <span>{note.folder || 'Top level'}</span>
            <span>·</span>
            <time dateTime={note.updated}>{dateTime(note.updated)}</time>
            {note.tags.map((tag) => (
              <Link key={tag} to={notesPath({ tag })} className="rounded-full bg-stone-200 px-2 py-0.5 hover:underline dark:bg-stone-800">
                #{tag}
              </Link>
            ))}
          </div>
        </li>
      ))}
    </ul>
  )
}

function SearchResults({ typed }: { typed: string }) {
  const text = useDebounced(typed.trim(), 200)
  const results = useQuery({ queryKey: ['search', text], queryFn: () => search(text), enabled: text.length >= SEARCH_MIN_CHARS })
  if (text.length < SEARCH_MIN_CHARS) return <p className="py-3 text-stone-500">Type at least {SEARCH_MIN_CHARS} characters.</p>
  if (results.isPending) return <p className="py-3 text-stone-500">Searching…</p>
  if (results.isError) return <p role="alert" className="py-3 text-rose-700 dark:text-rose-400">Search failed. Is the server still running?</p>
  if (results.data.length === 0) return <p className="py-3 text-stone-500">No matches.</p>
  return (
    <ul className="divide-y divide-stone-200 dark:divide-stone-800">
      {results.data.map((r) => (
        <li key={r.path} className="py-2.5">
          <Link to={focusPath(r.path)} className="block truncate font-medium hover:underline">
            {r.title}
          </Link>
          <div className="mt-0.5 text-xs text-stone-500">
            {r.kind === 'task' ? 'Task · ' : ''}
            {r.folder || 'Top level'}
          </div>
          <div className="mt-1 line-clamp-2">
            <Snippet parts={r.snippet} />
          </div>
        </li>
      ))}
    </ul>
  )
}

/** The search box. What's typed goes straight into the address (?q=), so a
 * search can be bookmarked and survives a reload; the search itself waits
 * until typing pauses. */
function SearchBox({ value }: { value: string }) {
  const navigate = useNavigate()
  return (
    <input
      type="search"
      aria-label="Search notes and tasks"
      placeholder="Search titles and text…"
      value={value}
      onChange={(e) => navigate(e.target.value === '' ? notesPath() : notesPath({ q: e.target.value }), { replace: true })}
      maxLength={200}
      className="mb-4 w-full rounded-lg border border-stone-300 bg-transparent px-3 py-2 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 dark:border-stone-700"
    />
  )
}

/** Mockup A's Notes: the folder tree on the left (resizable), the notes on the right. */
export default function Notes() {
  const [params] = useSearchParams()
  const folder = params.get('folder') ?? undefined
  const tag = params.get('tag') ?? undefined
  const q = params.get('q') ?? undefined
  const notes = useQuery({ queryKey: ['notes'], queryFn: getNotes })
  const sizes = useDefaultLayout({ id: 'onyx-notes', panelIds: ['tree', 'list'], storage: localStorage })

  if (notes.isPending) return <p className="text-stone-500">Loading…</p>
  if (notes.isError) {
    return (
      <p role="alert" className="text-rose-700 dark:text-rose-400">
        Notes couldn't be loaded. Is the server still running?
      </p>
    )
  }

  const tree = buildTree(notes.data)
  const shown = filterNotes(notes.data, { folder, tag })
  const heading = q !== undefined ? 'Search' : tag !== undefined ? `#${tag}` : folder ? folder : 'All notes'

  return (
    <Group orientation="horizontal" className="h-full" defaultLayout={sizes.defaultLayout} onLayoutChanged={sizes.onLayoutChanged}>
      <Panel id="tree" defaultSize="28%" minSize={180} maxSize="50%">
        <nav aria-label="Folders" className="h-full overflow-auto pr-3 text-sm">
          <ul>
            <FolderNode folder={tree} selected={tag === undefined ? (folder ?? '') : undefined} depth={0} />
          </ul>
        </nav>
      </Panel>
      <Separator className={SEPARATOR} />
      <Panel id="list" minSize="40%">
        <section aria-labelledby="notes-list-heading" className="h-full overflow-auto pl-4">
          <div className="mb-2 flex items-baseline gap-3">
            <h1 id="notes-list-heading" className="text-2xl font-semibold tracking-tight">
              {heading}
            </h1>
            {q === undefined && (
              <span className="text-sm text-stone-500">
                {shown.length} {shown.length === 1 ? 'note' : 'notes'}
              </span>
            )}
            {(q !== undefined || tag !== undefined || folder) && (
              <Link to={notesPath()} className="text-sm text-stone-500 underline">
                Show all
              </Link>
            )}
          </div>
          <SearchBox value={q ?? ''} />
          {q !== undefined ? <SearchResults typed={q} /> : <NoteList notes={shown} />}
        </section>
      </Panel>
    </Group>
  )
}
