import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { HomeData, Item, NoteDetail, NoteSummary } from './api'
import { LAYOUT_KEY } from './layout'
import { THEME_KEY } from './theme'

type Reply = { status: number; body?: unknown }
type Call = { path: string; method: string; body?: string }

const HOME: HomeData = {
  today: '2031-04-16',
  counts: { open: 4, 'in-progress': 3, 'in-review': 2, done: 3 },
  due: [
    { path: 'Tasks/a.md', title: 'Plan weekly sync agenda', status: 'in-progress', priority: 'high', due: '2031-04-15' },
  ],
  waiting: [
    { path: 'Tasks/b.md', title: 'Update release checklist', status: 'in-review', priority: 'low', due: null },
    { path: 'Tasks/c.md', title: 'Review cache rebuild design', status: 'in-review', priority: null, due: null },
  ],
  recent_notes: [
    { path: 'Projects/Atlas kickoff.md', title: 'Atlas kickoff', folder: 'Projects', updated: '2031-04-15T09:12:00+00:00' },
    { path: 'Inbox.md', title: 'Inbox', folder: '', updated: '2031-04-16T07:55:00+00:00' },
  ],
  history: [
    { at: '2031-04-14T20:00:00+00:00', path: 'Tasks/d.md', title: 'Fix broken wikilink', from: 'in-review', to: 'done', remark: 'signed off by owner' },
    { at: '2031-04-14T18:00:00+00:00', path: 'Tasks/d.md', title: 'Fix broken wikilink', from: 'created', to: 'open', remark: null },
  ],
}

const ITEMS: Item[] = [
  { kind: 'note', path: 'Projects/Atlas kickoff.md', title: 'Atlas kickoff' },
  { kind: 'task', path: 'Tasks/a.md', title: 'Plan weekly sync agenda' },
]

const NOTE: NoteDetail = {
  path: 'Projects/Atlas kickoff.md',
  title: 'Atlas kickoff',
  folder: 'Projects',
  kind: 'note',
  updated: '2031-04-15T09:12:00+00:00',
  tags: ['atlas', 'planning'],
  body: 'Atlas is a sample project.\n\n## Goals\n\n- Ship the **reading list**\n- See [[Atlas architecture]] and [[Nowhere]]\n\n`[[In code]]`',
  links: { 'Atlas architecture': 'Projects/Atlas architecture.md', Nowhere: null },
  backlinks: [{ path: 'Meetings/Weekly sync.md', title: 'Weekly sync' }],
  related_tasks: [{ path: 'Tasks/a.md', title: 'Plan weekly sync agenda', status: 'in-progress' }],
  task: null,
}

const TASK: NoteDetail = {
  path: 'Tasks/a.md',
  title: 'Plan weekly sync agenda',
  folder: 'Tasks',
  kind: 'task',
  updated: '2031-04-14T10:00:00+00:00',
  tags: [],
  body: 'Short description of the task.',
  links: {},
  backlinks: [],
  related_tasks: [],
  task: {
    status: 'in-progress',
    priority: 'high',
    due: '2031-04-15',
    projects: ['Atlas architecture'],
    created: '2031-04-13T11:00:00+00:00',
    completed: null,
    closed_by: null,
    time_to_close_minutes: null,
    history: [
      { at: '2031-04-13T11:00:00+00:00', from: 'created', to: 'open', remark: null },
      { at: '2031-04-13T12:00:00+00:00', from: 'open', to: 'in-progress', remark: null },
    ],
  },
}

function withNote(note: NoteDetail): Record<string, Reply> {
  return { [`GET /api/note?path=${encodeURIComponent(note.path)}`]: { status: 200, body: note } }
}

/** fetch that answers by method and path, recording every call. */
function fakeServer(routes: Record<string, Reply>) {
  const calls: Call[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init: RequestInit) => {
      const method = init.method ?? 'GET'
      calls.push({ path, method, body: init.body as string | undefined })
      const reply = routes[`${method} ${path}`]
      if (!reply) throw new Error(`unexpected call ${method} ${path}`)
      return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), { status: reply.status })
    }),
  )
  return calls
}

const signedIn = { 'GET /api/session': { status: 200, body: { authenticated: true } } }
const signedOut = { 'GET /api/session': { status: 200, body: { authenticated: false } } }
const withHome = { 'GET /api/home': { status: 200, body: HOME } }
const withItems = { 'GET /api/items': { status: 200, body: { items: ITEMS } } }

beforeEach(() => {
  localStorage.clear()
  window.history.replaceState(null, '', '/')
  document.documentElement.classList.remove('dark')
  window.history.replaceState(null, '', '/')
})
afterEach(() => vi.unstubAllGlobals())

describe('sign-in', () => {
  it('shows the sign-in form when not signed in', async () => {
    fakeServer(signedOut)
    render(<App />)
    expect(await screen.findByLabelText('Launch code')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled()
  })

  it('signs in with the code and shows Home', async () => {
    const calls = fakeServer({ ...signedOut, 'POST /api/session': { status: 204 }, ...withHome })
    render(<App />)
    await userEvent.type(await screen.findByLabelText('Launch code'), '  the-code  ')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Due today or overdue' })).toBeInTheDocument()
    const post = calls.find((c) => c.method === 'POST')
    expect(JSON.parse(post?.body ?? '')).toEqual({ code: 'the-code' })
  })

  it('explains a wrong or used code', async () => {
    fakeServer({ ...signedOut, 'POST /api/session': { status: 401, body: { detail: 'Invalid or expired launch code' } } })
    render(<App />)
    await userEvent.type(await screen.findByLabelText('Launch code'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/wrong, already used or expired/)
  })

  it('says when the server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/Can't reach the Onyx server/)
  })

  it('opens the launch-code help dialog', async () => {
    fakeServer(signedOut)
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Where do I find the code?' }))
    expect(await screen.findByRole('dialog', { name: 'Your launch code' })).toBeInTheDocument()
  })
})

describe('frame', () => {
  it('signs out from the top bar', async () => {
    const calls = fakeServer({ ...signedIn, ...withHome, 'DELETE /api/session': { status: 204 } })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByLabelText('Launch code')).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'DELETE' && c.path === '/api/session')).toBe(true)
  })

  it('forgets what it read from the vault when signing out', async () => {
    let homeCalls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string, init: RequestInit) => {
        const method = init.method ?? 'GET'
        if (path === '/api/session' && method === 'GET') return Response.json({ authenticated: true })
        if (path === '/api/session') return new Response(null, { status: 204 })
        if (path === '/api/home') {
          homeCalls += 1
          // First visit answers; after signing in again it never does, so only
          // data kept from before sign-out could appear.
          return homeCalls === 1 ? Response.json(HOME) : new Promise<Response>(() => {})
        }
        throw new Error(`unexpected call ${method} ${path}`)
      }),
    )
    render(<App />)
    expect(await screen.findByText('Atlas kickoff')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    await userEvent.type(await screen.findByLabelText('Launch code'), 'code')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect((await screen.findAllByText('Loading…')).length).toBeGreaterThan(0)
    expect(screen.queryByText('Atlas kickoff')).toBeNull()
  })

  it('goes back to sign-in when the session has ended', async () => {
    fakeServer({ ...signedIn, 'GET /api/home': { status: 401, body: { detail: 'Not signed in' } } })
    render(<App />)
    expect(await screen.findByLabelText('Launch code')).toBeInTheDocument()
  })

  it('shows a page for addresses that do not exist yet', async () => {
    window.history.replaceState(null, '', '/somewhere')
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Not here yet' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Back to Home' }))
    expect(await screen.findByRole('heading', { name: 'Due today or overdue' })).toBeInTheDocument()
  })
})

describe('theme', () => {
  it('toggles dark mode and remembers it', async () => {
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Switch to dark mode' }))
    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    await userEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
    expect(document.documentElement).not.toHaveClass('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('light')
  })

  it('starts from the remembered choice', async () => {
    localStorage.setItem(THEME_KEY, 'dark')
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Switch to light mode' })).toBeInTheDocument()
    expect(document.documentElement).toHaveClass('dark')
  })
})

describe('Home', () => {
  it('shows counts, due, waiting, recent notes and history', async () => {
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    expect(await screen.findByText(/Wednesday 16 April · 1 task due · 2 waiting for your sign-off/)).toBeInTheDocument()

    const stages = within(screen.getByRole('region', { name: 'Tasks by stage' }))
    expect(stages.getByText('In progress').previousSibling).toHaveTextContent('3')

    const due = within(screen.getByRole('region', { name: 'Due today or overdue' }))
    expect(due.getByText('Plan weekly sync agenda')).toBeInTheDocument()
    expect(due.getByText('15 Apr')).toBeInTheDocument()
    const waiting = within(screen.getByRole('region', { name: 'Waiting for your sign-off' }))
    expect(waiting.getByText('Update release checklist')).toBeInTheDocument()
    expect(due.queryByText('Update release checklist')).toBeNull()

    const notes = within(screen.getByRole('region', { name: 'Recent notes' }))
    expect(notes.getByText('Atlas kickoff')).toBeInTheDocument()

    // History is on Home's page and in the History panel beside it (shown by default).
    const inPage = within(within(screen.getByRole('main')).getByRole('region', { name: 'History' }))
    const inPanel = within(within(screen.getByRole('complementary', { name: 'Panels' })).getByRole('region', { name: 'History' }))
    for (const history of [inPage, inPanel]) {
      const rows = history.getAllByRole('listitem')
      expect(rows).toHaveLength(2)
      expect(rows[0]).toHaveTextContent('Fix broken wikilink')
      expect(rows[0]).toHaveTextContent('In review →Done')
      expect(rows[0]).toHaveTextContent('signed off by owner')
      expect(rows[1]).toHaveTextContent('created →Open')
    }
    expect(screen.getByRole('link', { name: 'Plan weekly sync agenda' })).toHaveAttribute(
      'href',
      '/focus?path=Tasks%2Fa.md',
    )
    expect(notes.getByRole('link', { name: 'Atlas kickoff' })).toHaveAttribute(
      'href',
      '/focus?path=Projects%2FAtlas%20kickoff.md',
    )
  })

  it('says when there is nothing to show', async () => {
    const empty: HomeData = {
      ...HOME,
      counts: { open: 0, 'in-progress': 0, 'in-review': 0, done: 0 },
      due: [],
      waiting: [],
      recent_notes: [],
      history: [],
    }
    fakeServer({ ...signedIn, 'GET /api/home': { status: 200, body: empty } })
    render(<App />)
    expect(await screen.findByText('All clear.')).toBeInTheDocument()
    expect(screen.getByText('Nothing waiting.')).toBeInTheDocument()
    expect(screen.getByText('No notes yet.')).toBeInTheDocument()
    expect(screen.getAllByText('No stage changes recorded yet.')).toHaveLength(2) // page and panel
    expect(screen.getByText(/0 tasks due · 0 waiting/)).toBeInTheDocument()
  })

  it('says when Home cannot be loaded', async () => {
    fakeServer({ ...signedIn, 'GET /api/home': { status: 500, body: { detail: 'boom' } } })
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent("Home couldn't be loaded")
  })

  it('shows vault text as text, never as HTML', async () => {
    const hostile = '<img src=x onerror=alert(1)>'
    fakeServer({
      ...signedIn,
      'GET /api/home': { status: 200, body: { ...HOME, waiting: [{ ...HOME.waiting[0], title: hostile }] } },
    })
    render(<App />)
    expect(await screen.findByText(hostile)).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
  })
})

describe('⌘K palette', () => {
  async function openWithKeys() {
    fakeServer({ ...signedIn, ...withHome, ...withItems })
    render(<App />)
    await screen.findByRole('heading', { name: 'Due today or overdue' })
    await userEvent.keyboard('{Meta>}k{/Meta}')
    return screen.findByRole('combobox', { name: 'Search notes, tasks and commands' })
  }

  it('opens with ⌘K and lists commands, notes and tasks', async () => {
    await openWithKeys()
    const list = within(screen.getByRole('listbox'))
    expect(await list.findByRole('option', { name: /Atlas kickoff/ })).toBeInTheDocument()
    expect(list.getByRole('option', { name: /Plan weekly sync agenda/ })).toBeInTheDocument()
    expect(list.getByRole('option', { name: /Sign out/ })).toBeInTheDocument()
    expect(list.getByRole('option', { name: /Hide panels/ })).toBeInTheDocument()
  })

  it('opens with Ctrl+K and from the top-bar button', async () => {
    fakeServer({ ...signedIn, ...withHome, ...withItems })
    render(<App />)
    await screen.findByRole('heading', { name: 'Due today or overdue' })
    await userEvent.keyboard('{Control>}k{/Control}')
    expect(await screen.findByRole('combobox')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('combobox')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: /Find anything/ }))
    expect(await screen.findByRole('combobox')).toBeInTheDocument()
  })

  it('filters as you type', async () => {
    const input = await openWithKeys()
    await screen.findByRole('option', { name: /Atlas kickoff/ })
    await userEvent.type(input, 'weekly')
    const options = screen.getAllByRole('option')
    expect(options).toHaveLength(1)
    expect(options[0]).toHaveTextContent('Plan weekly sync agenda')
    await userEvent.clear(input)
    await userEvent.type(input, 'zzz')
    expect(screen.getByText('No matches.')).toBeInTheDocument()
  })

  it('runs a command with Enter', async () => {
    const input = await openWithKeys()
    await userEvent.type(input, 'mode')
    expect(screen.getByRole('option', { name: /Switch to dark mode/ })).toHaveAttribute('aria-selected', 'true')
    await userEvent.keyboard('{Enter}')
    expect(document.documentElement).toHaveClass('dark')
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('moves the selection with the arrow keys, wrapping around', async () => {
    const input = await openWithKeys()
    await screen.findByRole('option', { name: /Atlas kickoff/ })
    const options = () => screen.getAllByRole('option')
    expect(options()[0]).toHaveAttribute('aria-selected', 'true')
    await userEvent.keyboard('{ArrowDown}')
    expect(options()[1]).toHaveAttribute('aria-selected', 'true')
    expect(input).toHaveAttribute('aria-activedescendant', options()[1].id)
    await userEvent.keyboard('{ArrowUp}{ArrowUp}')
    expect(options()[options().length - 1]).toHaveAttribute('aria-selected', 'true')
  })

  it('opens a note in the focus view', async () => {
    const calls = fakeServer({ ...signedIn, ...withHome, ...withItems, ...withNote(NOTE) })
    render(<App />)
    await screen.findByRole('heading', { name: 'Due today or overdue' })
    await userEvent.keyboard('{Meta>}k{/Meta}')
    await userEvent.type(await screen.findByRole('combobox'), 'atlas')
    await screen.findByRole('option', { name: /Atlas kickoff/ })
    await userEvent.keyboard('{Enter}')
    expect(await screen.findByRole('heading', { level: 1, name: 'Atlas kickoff' })).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).toBeNull()
    expect(calls.some((c) => c.path === '/api/note?path=Projects%2FAtlas%20kickoff.md')).toBe(true)
  })
})

function openFocus(note: NoteDetail) {
  window.history.replaceState(null, '', `/focus?path=${encodeURIComponent(note.path)}`)
}

describe('focus view', () => {
  it('reads a note, with its Markdown rendered', async () => {
    openFocus(NOTE)
    fakeServer({ ...signedIn, ...withHome, ...withNote(NOTE) })
    render(<App />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Atlas kickoff' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Goals' })).toBeInTheDocument()
    expect(screen.getByText('reading list').tagName).toBe('STRONG')
    expect(screen.getByRole('link', { name: 'Atlas architecture' })).toHaveAttribute(
      'href',
      '/focus?path=Projects%2FAtlas%20architecture.md',
    )
    expect(screen.getByText('Nowhere').tagName).toBe('SPAN') // no such note: not a link
    expect(screen.getByTitle('No note named "Nowhere"')).toBeInTheDocument()
    expect(screen.getByText('[[In code]]').tagName).toBe('CODE') // code is never a link
  })

  it('shows a task with its stage, priority and summary', async () => {
    openFocus(TASK)
    fakeServer({ ...signedIn, ...withHome, ...withNote(TASK) })
    render(<App />)
    expect(await screen.findByRole('heading', { level: 1, name: 'Plan weekly sync agenda' })).toBeInTheDocument()
    expect(screen.getByText('Tasks · Atlas architecture · due 15 Apr')).toBeInTheDocument()
    const main = within(screen.getByRole('main'))
    expect(main.getByText('In progress')).toBeInTheDocument()
    expect(main.getByText('High priority')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Summary' })).getByText('Short description of the task.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show all' })).toBeNull()
  })

  it('folds a long task description to a short summary', async () => {
    const long = { ...TASK, body: 'Long text. '.repeat(100) }
    openFocus(long)
    fakeServer({ ...signedIn, ...withHome, ...withNote(long) })
    render(<App />)
    const button = await screen.findByRole('button', { name: 'Show all' })
    expect(screen.getByTestId('summary-body')).toHaveClass('max-h-48')
    await userEvent.click(button)
    expect(screen.getByTestId('summary-body')).not.toHaveClass('max-h-48')
    expect(screen.getByRole('button', { name: 'Show less' })).toBeInTheDocument()
  })

  it('says when there is nothing at that address', async () => {
    window.history.replaceState(null, '', '/focus?path=Gone.md')
    fakeServer({ ...signedIn, ...withHome, 'GET /api/note?path=Gone.md': { status: 404, body: { detail: 'Note not found' } } })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Not found' })).toBeInTheDocument()
  })

  it('never turns note text into HTML or unsafe links', async () => {
    const hostile: NoteDetail = {
      ...NOTE,
      body: '<img src=x onerror=alert(1)>\n\n<script>alert(1)</script>\n\n[click](javascript:alert(1)) ![pic](http://example.com/x.png)',
    }
    openFocus(hostile)
    fakeServer({ ...signedIn, ...withHome, ...withNote(hostile) })
    render(<App />)
    const link = await screen.findByText('click')
    expect(link.getAttribute('href') ?? '').not.toMatch(/javascript/i)
    expect(document.querySelector('script:not([src])')).toBeNull()
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByText('[pic]')).toBeInTheDocument()
    // Raw HTML in a note is dropped, not shown as text.
    expect(screen.queryByText(/onerror|<script/i)).toBeNull()
  })
})

describe('panels', () => {
  it('shows Details and History by default, with the open task in both', async () => {
    openFocus(TASK)
    fakeServer({ ...signedIn, ...withHome, ...withNote(TASK) })
    render(<App />)
    const details = within(await screen.findByRole('region', { name: 'Details' }))
    expect(await details.findByText('Stage')).toBeInTheDocument()
    expect(details.getByText('Atlas architecture')).toBeInTheDocument()
    expect(details.getByText('still open')).toBeInTheDocument()
    const history = within(screen.getByRole('region', { name: 'History' }))
    const rows = history.getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Open →In progress') // newest first
  })

  it('History stays on Home when the panels are hidden', async () => {
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Panels' }))
    expect(screen.queryByRole('complementary', { name: 'Panels' })).toBeNull()
    expect(within(screen.getByRole('main')).getByRole('region', { name: 'History' })).toBeInTheDocument()
  })

  it('Details on Home asks you to open something', async () => {
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    const details = within(await screen.findByRole('region', { name: 'Details' }))
    expect(details.getByText('Open a note or task to see its details.')).toBeInTheDocument()
  })

  it('removes and adds panels, and remembers the choice', async () => {
    fakeServer({ ...signedIn, ...withHome })
    const { unmount } = render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Remove Details panel' }))
    expect(screen.queryByRole('region', { name: 'Details' })).toBeNull()
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY) ?? '{}').visible).toEqual(['backlinks', 'related-tasks', 'history'])

    unmount()
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    await screen.findByRole('region', { name: 'History' })
    expect(screen.queryByRole('region', { name: 'Details' })).toBeNull()

    // Radix menus open on pointer events jsdom doesn't fully support; the keyboard works the same.
    screen.getByRole('button', { name: '+ Add panel' }).focus()
    await userEvent.keyboard('{Enter}')
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Details' }))
    expect(await screen.findByRole('region', { name: 'Details' })).toBeInTheDocument()
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY) ?? '{}').visible).toEqual(['details', 'backlinks', 'related-tasks', 'history'])
  })

  it('hides and shows the side area', async () => {
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    const toggle = await screen.findByRole('button', { name: 'Panels' })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(toggle)
    expect(screen.queryByRole('complementary', { name: 'Panels' })).toBeNull()
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(JSON.parse(localStorage.getItem(LAYOUT_KEY) ?? '{}').sideOpen).toBe(false)
    await userEvent.click(toggle)
    expect(screen.getByRole('complementary', { name: 'Panels' })).toBeInTheDocument()
  })

  it('panel areas can be resized', async () => {
    fakeServer({ ...signedIn, ...withHome })
    render(<App />)
    await screen.findByRole('region', { name: 'Details' })
    // One between the page and the side area, one between each pair of the 4 default panels.
    expect(screen.getAllByRole('separator')).toHaveLength(4)
  })
})

const NOTES: NoteSummary[] = [
  { path: 'Projects/Atlas kickoff.md', title: 'Atlas kickoff', folder: 'Projects', updated: '2031-04-15T09:12:00+00:00', tags: ['atlas', 'planning'] },
  { path: 'Projects/Archive/Old plan.md', title: 'Old plan', folder: 'Projects/Archive', updated: '2031-03-01T09:00:00+00:00', tags: ['atlas'] },
  { path: 'Meetings/Weekly sync.md', title: 'Weekly sync', folder: 'Meetings', updated: '2031-04-16T10:00:00+00:00', tags: [] },
  { path: 'Inbox.md', title: 'Inbox', folder: '', updated: '2031-04-16T07:55:00+00:00', tags: ['planning'] },
]
const withNotes = { 'GET /api/notes': { status: 200, body: { notes: NOTES } } }

describe('Notes', () => {
  it('is in the navigation and lists every note, newest first', async () => {
    fakeServer({ ...signedIn, ...withHome, ...withNotes })
    render(<App />)
    await userEvent.click(await screen.findByRole('link', { name: 'Notes' }))
    expect(await screen.findByRole('heading', { name: 'All notes' })).toBeInTheDocument()
    const list = within(screen.getByRole('region', { name: 'All notes' }))
    expect(list.getAllByRole('listitem').map((li) => li.querySelector('a')?.textContent)).toEqual([
      'Weekly sync',
      'Inbox',
      'Atlas kickoff',
      'Old plan',
    ])
    expect(screen.getByText('4 notes')).toBeInTheDocument()
  })

  it('shows the folder tree, and a folder lists its notes and its subfolders\' notes', async () => {
    window.history.replaceState(null, '', '/notes')
    fakeServer({ ...signedIn, ...withHome, ...withNotes })
    render(<App />)
    const tree = within(await screen.findByRole('navigation', { name: 'Folders' }))
    await userEvent.click(tree.getByRole('link', { name: 'Projects' }))
    const list = within(await screen.findByRole('region', { name: 'Projects' }))
    expect(list.getAllByRole('listitem')).toHaveLength(2)
    expect(tree.getByRole('link', { name: 'Projects' })).toHaveAttribute('aria-current', 'page')
    expect(tree.getByRole('link', { name: 'Archive' })).toBeInTheDocument()
    await userEvent.click(tree.getByRole('button', { name: 'Collapse Projects' }))
    expect(tree.queryByRole('link', { name: 'Archive' })).toBeNull()
  })

  it('filters by tag from a note\'s tag', async () => {
    window.history.replaceState(null, '', '/notes')
    fakeServer({ ...signedIn, ...withHome, ...withNotes })
    render(<App />)
    const list = within(await screen.findByRole('region', { name: 'All notes' }))
    await userEvent.click(list.getAllByRole('link', { name: '#planning' })[0])
    const tagged = within(await screen.findByRole('region', { name: '#planning' }))
    expect(tagged.getAllByRole('listitem').map((li) => li.querySelector('a')?.textContent)).toEqual(['Inbox', 'Atlas kickoff'])
    await userEvent.click(screen.getByRole('link', { name: 'Show all' }))
    expect(await screen.findByRole('heading', { name: 'All notes' })).toBeInTheDocument()
  })

  it('shows note titles as text, never as HTML', async () => {
    window.history.replaceState(null, '', '/notes')
    const hostile = '<img src=x onerror=alert(1)>'
    fakeServer({ ...signedIn, ...withHome, 'GET /api/notes': { status: 200, body: { notes: [{ ...NOTES[0], title: hostile }] } } })
    render(<App />)
    expect((await screen.findAllByText(hostile)).length).toBeGreaterThan(0)
    expect(document.querySelector('img')).toBeNull()
  })
})

describe('note panels', () => {
  it('Backlinks and Related tasks show what links to the open note', async () => {
    openFocus(NOTE)
    fakeServer({ ...signedIn, ...withHome, ...withNote(NOTE) })
    render(<App />)
    const backlinks = within(await screen.findByRole('region', { name: 'Backlinks' }))
    expect(await backlinks.findByRole('link', { name: 'Weekly sync' })).toHaveAttribute('href', '/focus?path=Meetings%2FWeekly%20sync.md')
    const tasks = within(screen.getByRole('region', { name: 'Related tasks' }))
    expect(tasks.getByRole('link', { name: 'Plan weekly sync agenda' })).toBeInTheDocument()
    expect(tasks.getByText('In progress')).toBeInTheDocument()
  })

  it('say when nothing links to the note', async () => {
    openFocus(TASK)
    fakeServer({ ...signedIn, ...withHome, ...withNote(TASK) })
    render(<App />)
    expect(await screen.findByText('No notes link here.')).toBeInTheDocument()
    expect(screen.getByText('No tasks link here.')).toBeInTheDocument()
  })

  it('Tags can be added and lists every tag with its count', async () => {
    fakeServer({ ...signedIn, ...withHome, ...withNotes })
    render(<App />)
    ;(await screen.findByRole('button', { name: '+ Add panel' })).focus()
    await userEvent.keyboard('{Enter}')
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Tags' }))
    const tags = within(await screen.findByRole('region', { name: 'Tags' }))
    expect(await tags.findByRole('link', { name: '#atlas 2' })).toHaveAttribute('href', '/notes?tag=atlas')
    expect(tags.getByRole('link', { name: '#planning 2' })).toBeInTheDocument()
  })

  it('a tag in Details lists its notes', async () => {
    openFocus(NOTE)
    fakeServer({ ...signedIn, ...withHome, ...withNote(NOTE) })
    render(<App />)
    const details = within(await screen.findByRole('region', { name: 'Details' }))
    expect(await details.findByRole('link', { name: '#atlas' })).toHaveAttribute('href', '/notes?tag=atlas')
  })
})
