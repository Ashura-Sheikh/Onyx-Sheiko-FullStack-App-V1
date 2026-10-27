// Every call to the backend goes through apiFetch, so the security header and
// cookie handling can't be forgotten (threat model T1, T2).

import type { GetResponses, HistoryEntry, HomeData, Item, LaunchCode, NoteDetail, TaskSummary } from './api-types'

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

/**
 * A GET to an endpoint, typed from the backend's schema: the path decides the
 * response type (src/api-types.ts, generated; see scripts/gen-api-types.ts).
 */
export async function apiGet<P extends keyof GetResponses>(path: P, query?: Record<string, string>): Promise<GetResponses[P]> {
  // encodeURIComponent, not URLSearchParams: a space stays %20, as in every other address here.
  const search = query
    ? `?${Object.entries(query)
        .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
        .join('&')}`
    : ''
  const response = await apiFetch(`${path}${search}`)
  return (await response.json()) as GetResponses[P]
}

export async function getSession(): Promise<boolean> {
  const body = await apiGet('/api/session')
  return body.authenticated === true
}

export async function signIn(code: string): Promise<void> {
  const body: LaunchCode = { code }
  await apiFetch('/api/session', { method: 'POST', body: JSON.stringify(body) })
}

export async function signOut(): Promise<void> {
  await apiFetch('/api/session', { method: 'DELETE' })
}

// --- Types, all generated from the backend's response models -------------------

export type Stage = NonNullable<TaskSummary['status']>
export type Priority = NonNullable<TaskSummary['priority']>
export type { HistoryEntry, HomeData, Item, NoteDetail, TaskSummary }

export async function getHome(): Promise<HomeData> {
  return apiGet('/api/home')
}

export async function getItems(): Promise<Item[]> {
  return (await apiGet('/api/items')).items
}

export async function getNote(path: string): Promise<NoteDetail> {
  return apiGet('/api/note', { path })
}

/** The address of the focus view for a note or task. */
export function focusPath(path: string): string {
  return `/focus?path=${encodeURIComponent(path)}`
}
