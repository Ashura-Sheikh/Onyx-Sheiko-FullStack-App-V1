// Small helpers for creating, renaming and deleting notes (NoteActions.tsx).

import { ApiError, moveRefusal } from './api'

/** The message a refused write shows. */
export function writeProblem(error: unknown): string {
  const refusal = moveRefusal(error)
  if (refusal === 'exists') return 'A note with that name is already there. Choose another name.'
  if (refusal === 'changed') return 'This note changed on disk since it was opened, so nothing was changed. Open it again and retry.'
  if (error instanceof ApiError) {
    if (error.status === 401) return "You've been signed out, so nothing was changed."
    if (error.status === 404) return 'This note is no longer there (moved or deleted?).'
    return error.message
  }
  return 'That failed. Is the server still running?'
}

/** A note's name without its folder and .md, for the rename box. */
export function nameOf(path: string): string {
  return (path.split('/').pop() ?? path).replace(/\.md$/i, '')
}
