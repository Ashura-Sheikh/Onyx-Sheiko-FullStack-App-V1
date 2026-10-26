import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiFetch, CSRF_HEADER, getSession, signIn, signOut } from './api'

function mockFetch(response: Response) {
  const fn = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

describe('apiFetch', () => {
  it('always sends the security header and same-origin credentials', async () => {
    const fetchMock = mockFetch(new Response('{}', { status: 200 }))
    await apiFetch('/api/health')
    const [path, init] = fetchMock.mock.calls[0]
    expect(path).toBe('/api/health')
    expect(new Headers(init.headers).get(CSRF_HEADER)).toBe('1')
    expect(init.credentials).toBe('same-origin')
  })

  it('sends JSON content type when there is a body', async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }))
    await signIn('abc')
    const [, init] = fetchMock.mock.calls[0]
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toEqual({ code: 'abc' })
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
  })

  it('refuses anything that is not an API path', async () => {
    const fetchMock = mockFetch(new Response('{}'))
    await expect(apiFetch('https://example.com/api/x')).rejects.toThrow('Not an API path')
    await expect(apiFetch('/other')).rejects.toThrow('Not an API path')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('turns error responses into ApiError with the server message', async () => {
    mockFetch(new Response(JSON.stringify({ detail: 'Not signed in' }), { status: 401 }))
    const error = await apiFetch('/api/health').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(401)
    expect((error as ApiError).message).toBe('Not signed in')
  })
})

describe('session helpers', () => {
  it('getSession reads the authenticated flag', async () => {
    mockFetch(new Response(JSON.stringify({ authenticated: true })))
    await expect(getSession()).resolves.toBe(true)
  })

  it('signOut sends DELETE', async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }))
    await signOut()
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE')
  })
})
