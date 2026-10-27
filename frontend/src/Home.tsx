import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { focusPath, getHome, type TaskSummary } from './api'
import { dateTime, greeting, longDate, PRIORITY_DOT, PRIORITY_LABELS, shortDate, STAGE_LABELS, STAGES } from './labels'
import HistoryList from './HistoryList'
import { StagePill } from './StagePill'

const CARD = 'rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800'
const ROW_LINK = 'min-w-0 flex-1 truncate rounded hover:underline'

function TaskRow({ task, showDue }: { task: TaskSummary; showDue?: boolean }) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${task.priority ? PRIORITY_DOT[task.priority] : 'bg-stone-300 dark:bg-stone-700'}`}
        title={task.priority ? PRIORITY_LABELS[task.priority] : 'No priority'}
      />
      <Link to={focusPath(task.path)} className={ROW_LINK}>
        {task.title}
      </Link>
      {showDue && task.due && <span className="shrink-0 text-xs text-stone-500">{shortDate(task.due)}</span>}
      <StagePill stage={task.status} />
    </li>
  )
}

function TaskCard({ id, title, tasks, empty, showDue }: { id: string; title: string; tasks: TaskSummary[]; empty: string; showDue?: boolean }) {
  return (
    <section aria-labelledby={id} className={CARD}>
      <h2 id={id} className="mb-2 font-semibold">
        {title}
      </h2>
      {tasks.length === 0 ? (
        <p className="py-3 text-stone-500">{empty}</p>
      ) : (
        <ul className="divide-y divide-stone-200 dark:divide-stone-800">
          {tasks.map((task) => (
            <TaskRow key={task.path} task={task} showDue={showDue} />
          ))}
        </ul>
      )}
    </section>
  )
}

/** Mockup C's Home, using the full width. History is shown here and in the History panel. */
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

      <section aria-label="Tasks by stage" className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {STAGES.map((stage) => (
          <div key={stage} className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800">
            <div className="text-2xl font-semibold tabular-nums">{data.counts[stage]}</div>
            <div className="text-xs text-stone-500">{STAGE_LABELS[stage]}</div>
          </div>
        ))}
      </section>

      <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
        <TaskCard id="due-heading" title="Due today or overdue" tasks={data.due} empty="All clear." showDue />
        <TaskCard id="waiting-heading" title="Waiting for your sign-off" tasks={data.waiting} empty="Nothing waiting." />
        <section aria-labelledby="notes-heading" className={`${CARD} lg:col-span-2 2xl:col-span-1`}>
          <h2 id="notes-heading" className="mb-2 font-semibold">
            Recent notes
          </h2>
          {data.recent_notes.length === 0 ? (
            <p className="py-3 text-stone-500">No notes yet.</p>
          ) : (
            <ul className="space-y-3">
              {data.recent_notes.map((note) => (
                <li key={note.path}>
                  <Link to={focusPath(note.path)} className="block truncate hover:underline">
                    {note.title}
                  </Link>
                  <div className="text-xs text-stone-500">
                    {note.folder ? `${note.folder} · ` : ''}
                    {dateTime(note.updated)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-labelledby="history-heading" className={`${CARD} lg:col-span-2 2xl:col-span-3`}>
          <h2 id="history-heading" className="mb-1 font-semibold">
            History
          </h2>
          <p className="mb-2 text-sm text-stone-500">Latest stage changes across your tasks, newest first.</p>
          <HistoryList entries={data.history} empty="No stage changes recorded yet." />
        </section>
      </div>
    </>
  )
}
