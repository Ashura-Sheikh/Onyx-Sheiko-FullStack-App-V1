import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { checklistProgress, splitList, taskProblem } from './taskWrites'

describe('task write helpers', () => {
  it('splits comma-separated boxes, dropping blanks', () => {
    expect(splitList('a, b , ,c,')).toEqual(['a', 'b', 'c'])
    expect(splitList('   ')).toEqual([])
    expect(splitList('one')).toEqual(['one'])
  })

  it('progress counts ticked lines, or is null with none', () => {
    expect(checklistProgress([])).toBeNull()
    expect(checklistProgress([{ done: true }, { done: false }, { done: true }])).toEqual({ done: 2, total: 3 })
  })

  it('messages', () => {
    expect(taskProblem(new ApiError(409, 'x', { reason: 'exists' }))).toContain('already there')
    expect(taskProblem(new ApiError(409, 'x', { reason: 'changed' }))).toContain('changed on disk')
    expect(taskProblem(new ApiError(400, 'Refused.', { detail: 'Refused.' }))).toBe('Refused.')
    expect(taskProblem(new ApiError(401, 'x'))).toContain('signed out')
    expect(taskProblem(new ApiError(404, 'x'))).toContain('no longer there')
    expect(taskProblem(new TypeError('network'))).toContain('server still running')
  })
})
