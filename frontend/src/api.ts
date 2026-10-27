// Every call to the backend goes through apiFetch, so the security header and
// cookie handling can't be forgotten (threat model T1, T2).

export const CSRF_HEADER = 'X-Onyx-Request'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith('/api/')) throw new Error(`Not an API path: ${path}`)
  const headers = new Headers(init.headers)
  headers.set(CSRF_HEADER, '1')
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  // same-origin: the session cookie is only ever sent to this server.
  const response = await fetch(path, { ...init, headers, credentials: 'same-origin' })
  if (!response.ok) {
    let message = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') message = body.detail
    } catch {
      // not JSON; keep the status text
    }
    throw new ApiError(response.status, message)
  }
  return response
}

export async function getSession(): Promise<boolean> {
  const response = await apiFetch('/api/session')
  const body = (await response.json()) as { authenticated: boolean }
  return body.authenticated === true
}

export async function signIn(code: string): Promise<void> {
  await apiFetch('/api/session', { method: 'POST', body: JSON.stringify({ code }) })
}

export async function signOut(): Promise<void> {
  await apiFetch('/api/session', { method: 'DELETE' })
}
