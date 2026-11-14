// A task's sub-tasks: its own checklist lines (Sheikh's decision on #40). Shown
// inside the task's card and on its page; ticking writes "[x]" into the file,
// quoting the version read just before. A done task's checklist can't change.

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { addChecklistItem, getAppSettings, getNoteSource, setChecklistItem, type Stage } from './api'
import { checklistProgress, taskProblem } from './taskWrites'
import { READ_ONLY_REASON } from './taskMoves'

type Item = { text: string; done: boolean }
type Props = { path: string; status: Stage | null; items: Item[] }

export const DONE_REASON = 'This task is done, so its sub-tasks can’t change.'
/** How many sub-tasks a card shows before "+N more". */
export const CARD_ITEMS = 5

function useChecklist({ path, status }: Props) {
  const queryClient = useQueryClient()
  const app = useQuery({ queryKey: ['app-settings'], queryFn: getAppSettings, staleTime: Infinity })
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const blocked = app.data && !app.data.writable ? READ_ONLY_REASON : status === 'done' ? DONE_REASON : null

  async function run(write: (version: string) => Promise<unknown>): Promise<boolean> {
    if (busy || blocked || !app.data) return false
    setBusy(true)
    setProblem(null)
    try {
      await write((await getNoteSource(path)).version)
      return true
    } catch (error) {
      setProblem(taskProblem(error))
      return false
    } finally {
      await Promise.all([['tasks'], ['note', path], ['home']].map((queryKey) => queryClient.invalidateQueries({ queryKey })))
      setBusy(false)
    }
  }
  return { busy, problem, blocked: app.data ? blocked : 'Loading…', run }
}

function Problem({ text }: { text: string | null }) {
  if (!text) return null
  return (
    <p role="alert" className="mt-1 text-xs text-rose-700 dark:text-rose-400">
      {text}
    </p>
  )
}

function Rows({ props, shown, state }: { props: Props; shown: Item[]; state: ReturnType<typeof useChecklist> }) {
  return (
    <ul className="space-y-1">
      {shown.map((item, index) => (
        <li key={index} className="flex items-start gap-2">
          <input
            type="checkbox"
            checked={item.done}
            disabled={state.blocked !== null || state.busy}
            title={state.blocked ?? undefined}
            aria-label={item.text}
            onChange={() => {
              // Decided now: by the time the version arrives, React has reset the box.
              const done = !item.done
              void state.run((version) => setChecklistItem(props.path, index, done, version))
            }}
            className="mt-0.5 accent-emerald-600"
          />
          <span className={item.done ? 'text-stone-500 line-through' : undefined}>{item.text}</span>
        </li>
      ))}
    </ul>
  )
}

function Progress({ items }: { items: Item[] }) {
  const progress = checklistProgress(items)
  if (!progress) return null
  const { done, total } = progress
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-stone-500">
      <progress value={done} max={total} aria-label={`${done} of ${total} sub-tasks done`} className="h-1.5 w-12 accent-emerald-600" />
      {done}/{total}
    </span>
  )
}

/** Inside a card: progress, the first few sub-tasks with tick boxes, "+N more". */
export function CardChecklist(props: Props) {
  const state = useChecklist(props)
  if (props.items.length === 0) return null
  const more = props.items.length - CARD_ITEMS
  return (
    <div className="mt-2 text-sm" aria-label="Sub-tasks" role="group">
      <Progress items={props.items} />
      <div className="mt-1">
        <Rows props={props} shown={props.items.slice(0, CARD_ITEMS)} state={state} />
      </div>
      {more > 0 && <p className="mt-1 text-xs text-stone-500">+{more} more</p>}
      <Problem text={state.problem} />
    </div>
  )
}

/** On the task's page: every sub-task, and a box to add one. */
export function TaskChecklist(props: Props) {
  const state = useChecklist(props)
  const [text, setText] = useState('')

  async function add(event: FormEvent) {
    event.preventDefault()
    if (text.trim() === '') return
    if (await state.run((version) => addChecklistItem(props.path, text, version))) setText('')
  }

  return (
    <section aria-labelledby="subtasks-heading" className="mb-8">
      <h2 id="subtasks-heading" className="mb-2 flex items-center gap-3 text-sm font-medium tracking-wide text-stone-500 uppercase">
        Sub-tasks <Progress items={props.items} />
      </h2>
      {props.items.length === 0 ? <p className="mb-2 text-sm text-stone-500">No sub-tasks yet.</p> : <Rows props={props} shown={props.items} state={state} />}
      {state.blocked === null && (
        <form onSubmit={add} className="mt-2 flex gap-2">
          <input
            aria-label="New sub-task"
            placeholder="Add a sub-task…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={300}
            autoComplete="off"
            className="min-w-0 flex-1 rounded-lg border border-stone-300 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-emerald-600 dark:border-stone-700"
          />
          <button type="submit" disabled={state.busy || text.trim() === ''} className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-100 disabled:opacity-50 dark:border-stone-700 dark:hover:bg-stone-900">
            Add
          </button>
        </form>
      )}
      {state.blocked !== null && state.blocked !== 'Loading…' && <p className="mt-2 text-xs text-stone-500">{state.blocked}</p>}
      <Problem text={state.problem} />
    </section>
  )
}
