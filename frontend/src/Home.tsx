import { useQuery } from '@tanstack/react-query'
import { getHome, type HistoryEntry, type TaskSummary } from './api'
import {
  dateTime,
  greeting,
  isStage,
  longDate,
  PRIORITY_DOT,
  PRIORITY_LABELS,
  shortDate,
  STAGE_CLASSES,
  STAGE_LABELS,
  STAGES,
} from './labels'

const CARD =
  'rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800'

function StagePill({ stage }: { stage: TaskSummary['status'] }) {
  if (!stage) return null
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-medium ${STAGE_CLASSES[stage]}`}
    >
      {STAGE_LABELS[stage]}
    </span>
  )
}

// Rows aren't links yet: the focus view that opens a task arrives in the next part of #7.
function TaskRow({ task, showDue }: { task: TaskSummary; showDue?: boolean }) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${task.priority ? PRIORITY_DOT[task.priority] : 'bg-stone-300 dark:bg-stone-700'}`}
        title={task.priority ? PRIORITY_LABELS[task.priority] : 'No priority'}
      />
      <span className="min-w-0 flex-1 truncate">{task.title}</span>
      {showDue && task.due && <span className="shrink-0 text-xs text-stone-500">{shortDate(task.due)}</span>}
      <StagePill stage={task.status} />
    </li>
  )
}

function TaskList({ tasks, empty, showDue }: { tasks: TaskSummary[]; empty: string; showDue?: boolean }) {
  if (tasks.length === 0) return <p className="py-3 text-stone-500">{empty}</p>
  return (
    <ul className="divide-y divide-stone-200 dark:divide-stone-800">
      {tasks.map((task) => (
        <TaskRow key={task.path} task={task} showDue={showDue} />
      ))}
    </ul>
  )
}

function HistoryRow({ entry }: { entry: HistoryEntry }) {
  const from = isStage(entry.from) ? STAGE_LABELS[entry.from] : entry.from
  return (
    <li className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2.5">
      <time dateTime={entry.at} className="w-28 shrink-0 text-xs text-stone-500 tabular-nums">
        {dateTime(entry.at)}
      </time>
      <span className="min-w-0 flex-1 truncate">{entry.title}</span>
      <span className="flex shrink-0 items-center gap-1.5 text-xs text-stone-500">
        {from} →
        <StagePill stage={entry.to} />
      </span>
      {entry.remark && <span className="w-full pl-31 text-xs text-stone-500">{entry.remark}</span>}
    </li>
  )
}

export default function Home({ now = () => new Date() }: { now?: () => Date }) {
  const home = useQuery({ queryKey: ['home'], queryFn: getHome })

  if (home.isPending) return <p className="text-stone-500">Loading…</p>
  if (home.isError) {
    return (
      <p role="alert" className="text-rose-700 dark:text-rose-400">
        Home couldn't be loaded. Is the server still running?
      </p>
    )
  }

  const data = home.data
  return (
    <>
      <h1 className="mb-1 text-3xl font-semibold tracking-tight">{greeting(now().getHours())}</h1>
      <p className="mb-8 text-stone-500">
        {longDate(data.today)} · {data.due.length} {data.due.length === 1 ? 'task' : 'tasks'} due ·{' '}
        {data.waiting.length} waiting for your sign-off
      </p>

      <section aria-label="Tasks by stage" className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {STAGES.map((stage) => (
          <div key={stage} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800">
            <div className="text-2xl font-semibold tabular-nums">{data.counts[stage]}</div>
            <div className="text-xs text-stone-500">{STAGE_LABELS[stage]}</div>
          </div>
        ))}
      </section>

      <div className="grid gap-5 lg:grid-cols-3">
        <section aria-labelledby="due-heading" className={`${CARD} lg:col-span-2`}>
          <h2 id="due-heading" className="mb-2 font-semibold">
            Due today or overdue
          </h2>
          <TaskList tasks={data.due} empty="All clear." showDue />
          <h2 id="waiting-heading" className="mt-6 mb-2 font-semibold">
            Waiting for your sign-off
          </h2>
          <TaskList tasks={data.waiting} empty="Nothing waiting." />
        </section>

        <section aria-labelledby="notes-heading" className={CARD}>
          <h2 id="notes-heading" className="mb-2 font-semibold">
            Recent notes
          </h2>
          {data.recent_notes.length === 0 ? (
            <p className="py-3 text-stone-500">No notes yet.</p>
          ) : (
            <ul className="space-y-3">
              {data.recent_notes.map((note) => (
                <li key={note.path}>
                  <div className="truncate">{note.title}</div>
                  <div className="text-xs text-stone-500">
                    {note.folder ? `${note.folder} · ` : ''}
                    {dateTime(note.updated)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="history-heading" className={`${CARD} lg:col-span-3`}>
          <h2 id="history-heading" className="mb-1 font-semibold">
            History
          </h2>
          <p className="mb-2 text-sm text-stone-500">Latest stage changes across your tasks, newest first.</p>
          {data.history.length === 0 ? (
            <p className="py-3 text-stone-500">No stage changes recorded yet.</p>
          ) : (
            <ol className="divide-y divide-stone-200 dark:divide-stone-800">
              {data.history.map((entry, index) => (
                // A task can repeat the same line, so the position is part of the key.
                <HistoryRow key={`${index}|${entry.path}|${entry.at}`} entry={entry} />
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  )
}
