import { describe, expect, it } from 'vitest'
import { ApiError, type TaskCard } from './api'
import { hasSubtasksReason, noSubtasksReason, parentChoices, taskProblem } from './taskWrites'

const card = (over: Partial<TaskCard>): TaskCard => ({ path: 'Tasks/x.md', title: 'x', status: 'open', priority: null, due: null, projects: [], parent: null, subtasks: null, ...over })

describe('task write rules', () => {
  it('only a top-level task that isn’t done can take sub-tasks', () => {
    expect(noSubtasksReason(card({}))).toBeNull()
    expect(noSubtasksReason(card({ status: 'in-review' }))).toBeNull()
    expect(noSubtasksReason(card({ parent: { path: 'p', title: 'p' } }))).toContain('one level only')
    expect(noSubtasksReason(card({ status: 'done' }))).toContain('is done')
  })

  it('parent choices leave out sub-tasks and done tasks, sorted by title', () => {
    const tasks = [card({ path: 'b', title: 'B' }), card({ path: 'c', title: 'C', status: 'done' }), card({ path: 'a', title: 'A' }), card({ path: 'd', title: 'D', parent: { path: 'a', title: 'A' } })]
    expect(parentChoices(tasks).map((t) => t.path)).toEqual(['a', 'b'])
  })

  it('a task with sub-tasks can’t be renamed or deleted', () => {
    expect(hasSubtasksReason(card({}), 'rename')).toBeNull()
    expect(hasSubtasksReason(undefined, 'delete')).toBeNull()
    expect(hasSubtasksReason(card({ subtasks: { done: 0, total: 0 } }), 'delete')).toBeNull()
    expect(hasSubtasksReason(card({ subtasks: { done: 1, total: 1 } }), 'rename')).toContain('renamed')
    expect(hasSubtasksReason(card({ subtasks: { done: 1, total: 1 } }), 'delete')).toContain('Delete them first')
  })

  it('messages', () => {
    expect(taskProblem(new ApiError(409, 'x', { reason: 'exists' }))).toContain('already there')
    expect(taskProblem(new ApiError(409, 'x', { reason: 'changed' }))).toContain('changed on disk')
    expect(taskProblem(new ApiError(400, 'Bad line.', { detail: 'Bad line.', line: 3 }))).toBe('Bad line. (Unticked line 3 of the checklist.)')
    expect(taskProblem(new ApiError(409, 'Stopped.', { detail: 'Stopped.', created: ['a', 'b'] }))).toBe('Stopped. 2 made.')
    expect(taskProblem(new ApiError(400, 'Refused.', { detail: 'Refused.', line: null }))).toBe('Refused.')
    expect(taskProblem(new ApiError(401, 'x'))).toContain('signed out')
    expect(taskProblem(new TypeError('network'))).toContain('server still running')
  })
})
