// Filtering for the Tasks board and list (#9 part (a)). The filters live in
// the address (?view=list&status=…&priority=…&project=…), so a view can be
// bookmarked and survives a reload.

import type { Priority, Stage, TaskCard } from './api'
import { STAGES } from './labels'

export type TasksFilter = {
  view: 'board' | 'list'
  status?: Stage | 'none'
  priority?: Priority | 'none'
  project?: string
}

const PRIORITIES: Priority[] = ['high', 'normal', 'low']

/** Read the filter from the address; anything unknown is ignored. */
export function readFilter(params: URLSearchParams): TasksFilter {
  const status = params.get('status')
  const priority = params.get('priority')
  const project = params.get('project')
  return {
    view: params.get('view') === 'list' ? 'list' : 'board',
    status: status === 'none' || (STAGES as string[]).includes(status ?? '') ? (status as Stage | 'none') : undefined,
    priority: priority === 'none' || (PRIORITIES as string[]).includes(priority ?? '') ? (priority as Priority | 'none') : undefined,
    project: project !== null && project !== '' ? project : undefined,
  }
}

/** The address for a filter; the board and empty filters are left out. */
export function tasksPath(filter: TasksFilter): string {
  const parts: string[] = []
  if (filter.view === 'list') parts.push('view=list')
  if (filter.status) parts.push(`status=${encodeURIComponent(filter.status)}`)
  if (filter.priority) parts.push(`priority=${encodeURIComponent(filter.priority)}`)
  if (filter.project) parts.push(`project=${encodeURIComponent(filter.project)}`)
  return parts.length ? `/tasks?${parts.join('&')}` : '/tasks'
}

export function filterTasks(tasks: TaskCard[], filter: TasksFilter): TaskCard[] {
  return tasks.filter(
    (t) =>
      (filter.status === undefined || (t.status ?? 'none') === filter.status) &&
      (filter.priority === undefined || (t.priority ?? 'none') === filter.priority) &&
      (filter.project === undefined || t.projects.some((p) => p.toLowerCase() === filter.project!.toLowerCase())),
  )
}

/** Every project named by a task, once, sorted (case ignored, first spelling kept). */
export function projectsOf(tasks: TaskCard[]): string[] {
  const seen = new Map<string, string>()
  for (const t of tasks) for (const p of t.projects) if (!seen.has(p.toLowerCase())) seen.set(p.toLowerCase(), p)
  return [...seen.values()].sort((a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' }))
}

/** Board columns: the four stages, plus "No stage" only if a task has none. */
export function columns(tasks: TaskCard[]): (Stage | 'none')[] {
  return tasks.some((t) => t.status === null) ? [...STAGES, 'none'] : [...STAGES]
}
