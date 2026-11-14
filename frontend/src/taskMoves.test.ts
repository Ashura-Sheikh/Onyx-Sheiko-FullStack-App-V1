import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { moveProblem, nextStage } from './taskMoves'

describe('nextStage', () => {
  it.each([
    ['open', 'in-progress'],
    ['in-progress', 'in-review'],
    ['in-review', 'done'],
    ['done', null],
    [null, null],
  ] as const)('%s → %s', (stage, next) => expect(nextStage(stage)).toBe(next))
})

describe('moveProblem', () => {
  it.each([
    [new ApiError(409, 'x'), 'This task changed on disk since it was opened, so nothing was changed. Try again.'],
    [new ApiError(401, 'x'), "You've been signed out, so nothing was changed."],
    [new ApiError(404, 'x'), 'This task is no longer there (moved or deleted?).'],
    [new ApiError(400, "This task has sub-tasks that aren't done yet."), "This task has sub-tasks that aren't done yet."],
    [new Error('network'), 'That failed. Is the server still running?'],
  ])('%#', (error, text) => expect(moveProblem(error)).toBe(text))
})
