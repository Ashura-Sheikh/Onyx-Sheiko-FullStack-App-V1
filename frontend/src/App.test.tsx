import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

type Reply = { status: number; body?: unknown }

/** fetch that answers each call from a list, recording what was asked. */
function scriptedFetch(replies: Reply[]) {
  const calls: { path: string; method: string; body?: string }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (path: string, init: RequestInit) => {
      calls.push({ path, method: init.method ?? 'GET', body: init.body as string | undefined })
      const reply = replies.shift()
      if (!reply) throw new Error(`unexpected call ${path}`)
      return new Response(reply.body === undefined ? null : JSON.stringify(reply.body), {
        status: reply.status,
      })
    }),
  )
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('App', () => {
  it('shows the sign-in form when not signed in', async () => {
    scriptedFetch([{ status: 200, body: { authenticated: false } }])
    render(<App />)
    expect(await screen.findByLabelText('Launch code')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled()
  })

  it('signs in with the code and shows the signed-in page', async () => {
    const calls = scriptedFetch([{ status: 200, body: { authenticated: false } }, { status: 204 }])
    render(<App />)
    await userEvent.type(await screen.findByLabelText('Launch code'), '  the-code  ')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(/You're signed in/)).toBeInTheDocument()
    expect(calls[1]).toMatchObject({ path: '/api/session', method: 'POST' })
    expect(JSON.parse(calls[1].body ?? '')).toEqual({ code: 'the-code' })
  })

  it('explains a wrong or used code', async () => {
    scriptedFetch([
      { status: 200, body: { authenticated: false } },
      { status: 401, body: { detail: 'Invalid or expired launch code' } },
    ])
    render(<App />)
    await userEvent.type(await screen.findByLabelText('Launch code'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/wrong, already used or expired/)
  })

  it('goes straight to the signed-in page with a valid session', async () => {
    scriptedFetch([{ status: 200, body: { authenticated: true } }])
    render(<App />)
    expect(await screen.findByText(/You're signed in/)).toBeInTheDocument()
  })

  it('signs out', async () => {
    const calls = scriptedFetch([{ status: 200, body: { authenticated: true } }, { status: 204 }])
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByLabelText('Launch code')).toBeInTheDocument()
    expect(calls[1]).toMatchObject({ path: '/api/session', method: 'DELETE' })
  })

  it('says when the server cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent(/Can't reach the Onyx server/)
  })

  it('opens the launch-code help dialog', async () => {
    scriptedFetch([{ status: 200, body: { authenticated: false } }])
    render(<App />)
    await userEvent.click(await screen.findByRole('button', { name: 'Where do I find the code?' }))
    expect(await screen.findByRole('dialog', { name: 'Your launch code' })).toBeInTheDocument()
  })
})
