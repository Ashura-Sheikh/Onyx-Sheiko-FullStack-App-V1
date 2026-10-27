import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { focusPath, getNotes, notesPath } from '../api'
import { tagCounts } from '../notesTree'
import { StagePill } from '../StagePill'
import type { PanelContext } from './types'

const EMPTY = 'text-sm text-stone-500'
const LINK = 'block truncate text-sm text-violet-700 hover:underline dark:text-violet-400'

/** Notes that link to the open note. */
export function BacklinksPanel({ item }: PanelContext) {
  if (!item) return <p className={EMPTY}>Open a note to see what links to it.</p>
  if (item.backlinks.length === 0) return <p className={EMPTY}>No notes link here.</p>
  return (
    <ul className="space-y-1">
      {item.backlinks.map((note) => (
        <li key={note.path}>
          <Link to={focusPath(note.path)} className={LINK}>
            {note.title}
          </Link>
        </li>
      ))}
    </ul>
  )
}

/** Tasks that link to the open note, in their text or their `projects`. */
export function RelatedTasksPanel({ item }: PanelContext) {
  if (!item) return <p className={EMPTY}>Open a note to see its tasks.</p>
  if (item.related_tasks.length === 0) return <p className={EMPTY}>No tasks link here.</p>
  return (
    <ul className="space-y-1.5">
      {item.related_tasks.map((task) => (
        <li key={task.path} className="flex items-center justify-between gap-2">
          <Link to={focusPath(task.path)} className={`${LINK} min-w-0 flex-1`}>
            {task.title}
          </Link>
          <StagePill stage={task.status} />
        </li>
      ))}
    </ul>
  )
}

/** Every tag in the vault's notes with its count; a tag lists its notes. */
export function TagsPanel() {
  const notes = useQuery({ queryKey: ['notes'], queryFn: getNotes })
  if (notes.isPending) return <p className={EMPTY}>Loading…</p>
  if (notes.isError) return <p className="text-sm text-rose-700 dark:text-rose-400">Tags couldn't be loaded.</p>
  const tags = tagCounts(notes.data)
  if (tags.length === 0) return <p className={EMPTY}>No tags yet.</p>
  return (
    <ul className="flex flex-wrap gap-1.5">
      {tags.map(({ tag, count }) => (
        <li key={tag}>
          <Link
            to={notesPath({ tag })}
            className="inline-flex items-center gap-1 rounded-full bg-stone-200 px-2 py-0.5 text-xs hover:underline dark:bg-stone-800"
          >
            #{tag} <span className="text-stone-500">{count}</span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
