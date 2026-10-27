import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ApiError, getNote, type NoteDetail } from './api'
import { useCurrentItem } from './currentItem'
import { dateTime, shortDate } from './labels'
import Markdown, { type ResolvedLinks } from './Markdown'
import NoteEditor, { type Leaving } from './NoteEditor'
import { PriorityPill, StagePill } from './StagePill'

// Longer task bodies start folded to a short summary.
export const SUMMARY_CHARS = 600

function TaskSummary({ body, links }: { body: string; links: ResolvedLinks }) {
  const [expanded, setExpanded] = useState(false)
  if (body.trim() === '') return <p className="text-stone-500">No description.</p>
  const long = body.length > SUMMARY_CHARS
  return (
    <section aria-labelledby="summary-heading">
      <h2 id="summary-heading" className="mb-1 text-sm font-medium tracking-wide text-stone-500 uppercase">
        Summary
      </h2>
      <div
        data-testid="summary-body"
        className={long && !expanded ? 'relative max-h-48 overflow-hidden' : undefined}
      >
        <Markdown text={body} links={links} />
        {long && !expanded && (
          <div className="absolute inset-x-0 bottom-0 h-12 bg-linear-to-t from-stone-50 dark:from-stone-950" />
        )}
      </div>
      {long && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="mt-2 text-sm text-emerald-700 underline dark:text-emerald-400"
        >
          {expanded ? 'Show less' : 'Show all'}
        </button>
      )}
    </section>
  )
}

type Mode = 'read' | 'edit'

function ModeSwitch({ mode, onChange }: { mode: Mode; onChange: (mode: Mode) => void }) {
  return (
    <div role="group" aria-label="Mode" className="inline-flex rounded-full border border-stone-300 p-0.5 text-sm dark:border-stone-700">
      {(['read', 'edit'] as const).map((m) => (
        <button
          key={m}
          type="button"
          aria-pressed={mode === m}
          onClick={() => onChange(m)}
          className={`rounded-full px-3 py-1 ${mode === m ? 'bg-stone-200 font-medium dark:bg-stone-800' : 'text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-900'}`}
        >
          {m === 'read' ? 'Read' : 'Edit'}
        </button>
      ))}
    </div>
  )
}

function FocusItem({ item }: { item: NoteDetail }) {
  const [mode, setModeNow] = useState<Mode>('read')
  const [dirty, setDirty] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const leaving: Leaving = { dirty, setDirty, confirm, setConfirm }
  function setMode(next: Mode) {
    // Leaving the editor with unsaved text asks first (in the editor).
    if (mode === 'edit' && next === 'read' && dirty) return setConfirm(true)
    setModeNow(next)
  }
  function closeEditor() {
    setDirty(false)
    setConfirm(false)
    setModeNow('read')
  }
  const task = item.task
  const where = [item.folder, task?.projects.join(', ')].filter(Boolean).join(' · ')
  return (
    <article className="mx-auto max-w-3xl">
      <div className="mb-2 flex items-center gap-3 text-sm text-stone-500">
        <span className="min-w-0 flex-1 truncate">
          {where && `${where} · `}
          {task?.due ? `due ${shortDate(task.due)}` : `updated ${dateTime(item.updated)}`}
        </span>
        {/* Read while editing goes through the editor, which asks before dropping unsaved text. */}
        <ModeSwitch mode={mode} onChange={setMode} />
      </div>
      <h1 className={`mb-4 tracking-tight ${task ? 'text-3xl font-semibold' : 'font-serif text-4xl'}`}>{item.title}</h1>
      {mode === 'edit' ? (
        <NoteEditor path={item.path} leaving={leaving} onClose={closeEditor} />
      ) : task ? (
        <>
          <div className="mb-8 flex flex-wrap gap-1.5">
            <StagePill stage={task.status} />
            <PriorityPill priority={task.priority} />
          </div>
          <TaskSummary body={item.body} links={item.links} />
        </>
      ) : (
        <div className="font-serif text-lg leading-8">
          {item.body.trim() === '' ? <p className="text-stone-500">This note is empty.</p> : <Markdown text={item.body} links={item.links} />}
        </div>
      )}
    </article>
  )
}

/** Mockup C's focus view: one note or task, full width. Read, or Edit its body. */
export default function Focus() {
  const [params] = useSearchParams()
  const path = params.get('path') ?? ''
  const { setItem } = useCurrentItem()
  const note = useQuery({ queryKey: ['note', path], queryFn: () => getNote(path), enabled: path !== '' })

  useEffect(() => {
    setItem(note.data ?? null)
  }, [note.data, setItem])
  useEffect(() => () => setItem(null), [setItem])

  if (path === '' || (note.isError && note.error instanceof ApiError && note.error.status === 404)) {
    return (
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-2 text-2xl font-semibold tracking-tight">Not found</h1>
        <p className="text-stone-500">
          There's no note or task here. It may have been moved or renamed.{' '}
          <Link to="/" className="underline">
            Back to Home
          </Link>
        </p>
      </div>
    )
  }
  if (note.isPending) return <p className="text-stone-500">Loading…</p>
  if (note.isError) {
    return (
      <p role="alert" className="text-rose-700 dark:text-rose-400">
        This couldn't be loaded. Is the server still running?
      </p>
    )
  }
  // A different note starts in Read mode.
  return <FocusItem key={note.data.path} item={note.data} />
}
