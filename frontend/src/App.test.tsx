import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import type { HomeData, Item } from './api'
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
    expect(await screen.findByText('Loading…')).toBeInTheDocument()
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
    expect(await screen.findByRole('heading', { name: 'History' })).toBeInTheDocument()
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
    expect(due.getByText('Update release checklist')).toBeInTheDocument()

    const notes = within(screen.getByRole('region', { name: 'Recent notes' }))
    expect(notes.getByText('Atlas kickoff')).toBeInTheDocument()

    const history = within(screen.getByRole('region', { name: 'History' }))
    const rows = history.getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('Fix broken wikilink')
    expect(rows[0]).toHaveTextContent('In review →Done')
    expect(rows[0]).toHaveTextContent('signed off by owner')
    expect(rows[1]).toHaveTextContent('created →Open')
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
    expect(screen.getByText('No stage changes recorded yet.')).toBeInTheDocument()
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
    await screen.findByRole('heading', { name: 'History' })
    await userEvent.keyboard('{Meta>}k{/Meta}')
    return screen.findByRole('combobox', { name: 'Search notes, tasks and commands' })
  }

  it('opens with ⌘K and lists commands, notes and tasks', async () => {
    await openWithKeys()
    const list = within(screen.getByRole('listbox'))
    expect(await list.findByRole('option', { name: /Atlas kickoff/ })).toHaveAttribute('aria-disabled', 'true')
    expect(list.getByRole('option', { name: /Sign out/ })).toHaveAttribute('aria-disabled', 'false')
  })

  it('opens with Ctrl+K and from the top-bar button', async () => {
    fakeServer({ ...signedIn, ...withHome, ...withItems })
    render(<App />)
    await screen.findByRole('heading', { name: 'History' })
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

  it('does nothing yet when a note is chosen', async () => {
    const input = await openWithKeys()
    await userEvent.type(input, 'atlas')
    await screen.findByRole('option', { name: /Atlas kickoff/ })
    await userEvent.keyboard('{Enter}')
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })
})
