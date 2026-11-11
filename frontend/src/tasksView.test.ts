import { describe, expect, it } from 'vitest'
import type { TaskCard } from './api'
import { columns, filterTasks, projectsOf, readFilter, tasksPath } from './tasksView'

const card = (over: Partial<TaskCard>): TaskCard => ({
  path: 'T.md',
  title: 'T',
  status: 'open',
  priority: null,
  due: null,
  projects: [],
  parent: null,
  subtasks: null,
  ...over,
})

describe('readFilter and tasksPath', () => {
  it('the board with no filters is plain /tasks', () => {
    expect(readFilter(new URLSearchParams(''))).toEqual({ view: 'board', status: undefined, priority: undefined, project: undefined })
    expect(tasksPath({ view: 'board' })).toBe('/tasks')
  })

  it('round-trips every filter through the address', () => {
    const filter = { view: 'list', status: 'in-review', priority: 'none', project: 'Atlas & co' } as const
    const path = tasksPath(filter)
    expect(path).toBe('/tasks?view=list&status=in-review&priority=none&project=Atlas%20%26%20co')
    expect(readFilter(new URLSearchParams(path.split('?')[1]))).toEqual(filter)
  })

  it('ignores values it does not know', () => {
    expect(readFilter(new URLSearchParams('view=grid&status=later&priority=urgent&project='))).toEqual({
      view: 'board',
      status: undefined,
      priority: undefined,
      project: undefined,
    })
  })
})

describe('filterTasks', () => {
  const tasks = [
    card({ path: 'a', status: 'open', priority: 'high', projects: ['Atlas'] }),
    card({ path: 'b', status: 'done', priority: null, projects: ['Harbor'] }),
    card({ path: 'c', status: null, priority: 'low', projects: [] }),
  ]
  const paths = (f: Parameters<typeof filterTasks>[1]) => filterTasks(tasks, f).map((t) => t.path)

  it('by stage, including "none"', () => {
    expect(paths({ view: 'board', status: 'done' })).toEqual(['b'])
    expect(paths({ view: 'board', status: 'none' })).toEqual(['c'])
  })

  it('by priority, including "none"', () => {
    expect(paths({ view: 'board', priority: 'high' })).toEqual(['a'])
    expect(paths({ view: 'board', priority: 'none' })).toEqual(['b'])
  })

  it('by project, ignoring case', () => {
    expect(paths({ view: 'board', project: 'atlas' })).toEqual(['a'])
  })

  it('combines filters', () => {
    expect(paths({ view: 'list', status: 'open', project: 'Harbor' })).toEqual([])
    expect(paths({ view: 'list' })).toEqual(['a', 'b', 'c'])
  })
})

describe('projectsOf and columns', () => {
  it('lists each project once, sorted, keeping the first spelling', () => {
    expect(projectsOf([card({ projects: ['harbor', 'Atlas'] }), card({ projects: ['Harbor', 'beta'] })])).toEqual(['Atlas', 'beta', 'harbor'])
  })

  it('adds a "No stage" column only when a task has none', () => {
    expect(columns([card({ status: 'open' })])).toEqual(['open', 'in-progress', 'in-review', 'done'])
    expect(columns([card({ status: null })])).toEqual(['open', 'in-progress', 'in-review', 'done', 'none'])
  })
})
