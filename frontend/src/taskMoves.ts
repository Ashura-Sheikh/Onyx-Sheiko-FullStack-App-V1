// Rules and messages for moving a task one stage on (TaskMove.tsx).

import { ApiError, type Stage } from './api'
import { STAGES } from './labels'

/** The stage after `stage`, or null at done or for an unknown stage. */
export function nextStage(stage: Stage | null): Stage | null {
  if (stage === null) return null
  return STAGES[STAGES.indexOf(stage) + 1] ?? null
}

export function moveProblem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return 'This task changed on disk since it was opened, so nothing was changed. Try again.'
    if (error.status === 401) return "You've been signed out, so nothing was changed."
    if (error.status === 404) return 'This task is no longer there (moved or deleted?).'
    return error.message
  }
  return 'That failed. Is the server still running?'
}

export const READ_ONLY_REASON = 'Read-only: the server was started without --allow-writes.'
export const NO_IDENTITY_REASON = 'Sign-off needs a name: start the server with --identity NAME.'
