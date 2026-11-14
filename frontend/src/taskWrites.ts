// Messages and small helpers for task writes (TaskActions.tsx, Checklist.tsx; #9 part (c)).

import { ApiError, moveRefusal } from './api'

/** The message a refused task write shows. */
export function taskProblem(error: unknown): string {
  const refusal = moveRefusal(error)
  if (refusal === 'exists') return 'A note or task with that name is already there. Choose another name.'
  if (refusal === 'changed') return 'This task changed on disk since it was opened, so nothing was changed. Try again.'
  if (error instanceof ApiError) {
    if (error.status === 401) return "You've been signed out, so nothing was changed."
    if (error.status === 404) return 'This task is no longer there (moved or deleted?).'
    return error.message
  }
  return 'That failed. Is the server still running?'
}

/** "a, b , ,c" → ["a", "b", "c"]: the comma-separated boxes in Edit details. */
export function splitList(text: string): string[] {
  return text
    .split(',')
    .map((part) => part.trim())
    .filter((part) => part !== '')
}

/** "2/3" for a checklist, or null if there isn't one. */
export function checklistProgress(items: { done: boolean }[]): { done: number; total: number } | null {
  if (items.length === 0) return null
  return { done: items.filter((i) => i.done).length, total: items.length }
}
