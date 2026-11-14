// Rules and messages for creating, renaming and deleting tasks (TaskActions.tsx, #9 part (c)).

import { ApiError, moveRefusal, type TaskCard } from './api'

/** The message a refused task write shows. A refusal about one checklist line says which. */
export function taskProblem(error: unknown): string {
  const refusal = moveRefusal(error)
  if (refusal === 'exists') return 'A note or task with that name is already there. Choose another name.'
  if (refusal === 'changed') return 'This task changed on disk since it was opened, so nothing was changed. Open it again and retry.'
  if (error instanceof ApiError) {
    if (error.status === 401) return "You've been signed out, so nothing was changed."
    if (error.status === 404) return 'This task is no longer there (moved or deleted?).'
    const line = (error.body as { line?: unknown } | undefined)?.line
    if (typeof line === 'number') return `${error.message} (Unticked line ${line} of the checklist.)`
    const created = (error.body as { created?: unknown } | undefined)?.created
    if (Array.isArray(created)) return `${error.message} ${created.length} made.`
    return error.message
  }
  return 'That failed. Is the server still running?'
}

/** Why a task can't take new sub-tasks, or null if it can (one level only; not once done). */
export function noSubtasksReason(task: Pick<TaskCard, 'parent' | 'status'>): string | null {
  if (task.parent) return "A sub-task can't have sub-tasks of its own: one level only."
  if (task.status === 'done') return 'This task is done, so it can’t get new sub-tasks.'
  return null
}

/** Tasks a new task can be a sub-task of, by title. */
export function parentChoices(tasks: TaskCard[]): TaskCard[] {
  return tasks.filter((t) => noSubtasksReason(t) === null).sort((a, b) => a.title.localeCompare(b.title))
}

/** Why a task can't be renamed or deleted here, or null if it can. */
export function hasSubtasksReason(task: Pick<TaskCard, 'subtasks'> | undefined, what: 'rename' | 'delete'): string | null {
  if (!task?.subtasks || task.subtasks.total === 0) return null
  return what === 'rename'
    ? 'This task has sub-tasks, so it can’t be renamed: their links to it would stop working.'
    : 'This task has sub-tasks, so it can’t be deleted. Delete them first.'
}
