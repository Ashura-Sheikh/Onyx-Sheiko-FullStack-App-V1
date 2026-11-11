import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { nameOf, writeProblem } from './noteWrites'

describe('nameOf', () => {
  it.each([
    ['Projects/Atlas kickoff.md', 'Atlas kickoff'],
    ['Inbox.md', 'Inbox'],
    ['A/B/Upper.MD', 'Upper'],
    ['Projects/v1.md.md', 'v1.md'],
  ])('%s → %s', (path, name) => expect(nameOf(path)).toBe(name))
})

describe('writeProblem', () => {
  it.each([
    [new ApiError(409, 'x', { reason: 'exists' }), 'A note with that name is already there. Choose another name.'],
    [new ApiError(409, 'x', { reason: 'changed' }), 'This note changed on disk since it was opened, so nothing was changed. Open it again and retry.'],
    [new ApiError(409, 'Something else', { reason: 'other' }), 'Something else'],
    [new ApiError(401, 'x'), "You've been signed out, so nothing was changed."],
    [new ApiError(404, 'x'), 'This note is no longer there (moved or deleted?).'],
    [new ApiError(400, 'A note name can\'t start with a dot.'), "A note name can't start with a dot."],
    [new Error('network'), 'That failed. Is the server still running?'],
  ])('%#', (error, text) => expect(writeProblem(error)).toBe(text))
})
