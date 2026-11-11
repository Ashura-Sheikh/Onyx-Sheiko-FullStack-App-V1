import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { focusPath, getTasks, type Priority, type Stage, type TaskCard } from './api'
import { PRIORITY_LABELS, shortDate, STAGE_LABELS } from './labels'
import { PriorityPill, StagePill } from './StagePill'
import TaskMove from './TaskMove'
import { columns, filterTasks, projectsOf, readFilter, tasksPath, type TasksFilter } from './tasksView'

const SELECT =
  'rounded-lg border border-stone-300 bg-transparent px-2 py-1 text-sm outline-none focus:border-emerald-600 dark:border-stone-700 dark:bg-stone-950'
const columnLabel = (stage: Stage | 'none') => (stage === 'none' ? 'No stage' : STAGE_LABELS[stage])

function Subtasks({ task }: { task: TaskCard }) {
  if (!task.subtasks) return null
  const { done, total } = task.subtasks
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-stone-500">
      <progress value={done} max={total} aria-label={`${done} of ${total} sub-tasks done`} className="h-1.5 w-12 accent-emerald-600" />
      {done}/{total} sub-tasks
    </span>
  )
}

function Parent({ task }: { task: TaskCard }) {
  if (!task.parent) return null
  return (
    <span className="block truncate text-xs text-stone-500">
      ↳ Sub-task of{' '}
      <Link to={focusPath(task.parent.path)} className="hover:underline">
        {task.parent.title}
      </Link>
    </span>
  )
}

/** Mockup B's card: title, priority, due date, project, parent or sub-task progress. */
function Card({ task }: { task: TaskCard }) {
  return (
    <li className="rounded-xl bg-white p-3 shadow-sm ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800">
      <Parent task={task} />
      <Link to={focusPath(task.path)} className="block font-medium hover:underline">
        {task.title}
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-stone-500">
        <PriorityPill priority={task.priority} />
        {task.due && <time dateTime={task.due}>due {shortDate(task.due)}</time>}
        {task.projects.map((p) => (
          <span key={p} className="rounded-full bg-stone-100 px-2 py-0.5 dark:bg-stone-800">
            {p}
          </span>
        ))}
        <Subtasks task={task} />
      </div>
      <TaskMove task={task} />
    </li>
  )
}

function Board({ tasks, all }: { tasks: TaskCard[]; all: TaskCard[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {columns(all).map((stage) => {
        const here = tasks.filter((t) => (t.status ?? 'none') === stage)
        return (
          <section key={stage} aria-label={columnLabel(stage)} className="min-w-0 rounded-2xl bg-stone-100 p-3 dark:bg-stone-900/50">
            <h2 className="mb-2 flex items-center justify-between text-sm font-medium">
              {columnLabel(stage)} <span className="text-stone-500">{here.length}</span>
            </h2>
            {here.length === 0 ? (
              <p className="text-sm text-stone-500">Nothing here.</p>
            ) : (
              <ul className="space-y-2">
                {here.map((t) => (
                  <Card key={t.path} task={t} />
                ))}
              </ul>
            )}
          </section>
        )
      })}
    </div>
  )
}

function List({ tasks }: { tasks: TaskCard[] }) {
  if (tasks.length === 0) return <p className="text-stone-500">No tasks match.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-stone-500 uppercase">
          <tr>
            <th className="py-2 pr-3 font-medium">Task</th>
            <th className="py-2 pr-3 font-medium">Stage</th>
            <th className="py-2 pr-3 font-medium">Priority</th>
            <th className="py-2 pr-3 font-medium">Due</th>
            <th className="py-2 pr-3 font-medium">Projects</th>
            <th className="py-2 pr-3 font-medium">Next</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-200 dark:divide-stone-800">
          {tasks.map((t) => (
            <tr key={t.path}>
              <td className="py-2 pr-3">
                <Parent task={t} />
                <Link to={focusPath(t.path)} className="font-medium hover:underline">
                  {t.title}
                </Link>
                <div>
                  <Subtasks task={t} />
                </div>
              </td>
              <td className="py-2 pr-3">{t.status ? <StagePill stage={t.status} /> : <span className="text-stone-500">No stage</span>}</td>
              <td className="py-2 pr-3">
                <PriorityPill priority={t.priority} />
              </td>
              <td className="py-2 pr-3 whitespace-nowrap">{t.due ? shortDate(t.due) : ''}</td>
              <td className="py-2 pr-3">{t.projects.join(', ')}</td>
              <td className="py-2 pr-3">
                <TaskMove task={t} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Tasks (#9): mockup B's board by stage (the default) or a list, read-only, with filters. */
export default function Tasks() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const filter = readFilter(params)
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: getTasks })
  const go = (change: Partial<TasksFilter>) => navigate(tasksPath({ ...filter, ...change }), { replace: true })

  if (tasks.isPending) return <p className="text-stone-500">Loading…</p>
  if (tasks.isError) {
    return (
      <p role="alert" className="text-rose-700 dark:text-rose-400">
        Tasks couldn't be loaded. Is the server still running?
      </p>
    )
  }
  const shown = filterTasks(tasks.data, filter)
  const filtered = filter.status !== undefined || filter.priority !== undefined || filter.project !== undefined

  return (
    <section aria-labelledby="tasks-heading">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 id="tasks-heading" className="text-2xl font-semibold tracking-tight">
          Tasks
        </h1>
        <span className="text-sm text-stone-500">
          {shown.length} of {tasks.data.length}
        </span>
        <div role="group" aria-label="View" className="ml-auto inline-flex rounded-full border border-stone-300 p-0.5 text-sm dark:border-stone-700">
          {(['board', 'list'] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={filter.view === v}
              onClick={() => go({ view: v })}
              className={`rounded-full px-3 py-1 ${filter.view === v ? 'bg-stone-200 font-medium dark:bg-stone-800' : 'text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-900'}`}
            >
              {v === 'board' ? 'Board' : 'List'}
            </button>
          ))}
        </div>
      </div>
      <div role="group" aria-label="Filters" className="mb-4 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1.5 text-sm">
          Stage
          <select className={SELECT} value={filter.status ?? ''} onChange={(e) => go({ status: (e.target.value || undefined) as TasksFilter['status'] })}>
            <option value="">All</option>
            {columns(tasks.data).map((s) => (
              <option key={s} value={s}>
                {columnLabel(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-sm">
          Priority
          <select className={SELECT} value={filter.priority ?? ''} onChange={(e) => go({ priority: (e.target.value || undefined) as TasksFilter['priority'] })}>
            <option value="">All</option>
            {(['high', 'normal', 'low'] as Priority[]).map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABELS[p].replace(' priority', '')}
              </option>
            ))}
            <option value="none">None</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-sm">
          Project
          <select className={SELECT} value={filter.project ?? ''} onChange={(e) => go({ project: e.target.value || undefined })}>
            <option value="">All</option>
            {projectsOf(tasks.data).map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        {filtered && (
          <Link to={tasksPath({ view: filter.view })} className="text-sm text-stone-500 underline">
            Clear filters
          </Link>
        )}
      </div>
      {filter.view === 'list' ? <List tasks={shown} /> : <Board tasks={shown} all={tasks.data} />}
    </section>
  )
}
