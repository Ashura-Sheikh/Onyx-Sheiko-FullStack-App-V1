// Every call to the backend goes through apiFetch, so the security header and
// cookie handling can't be forgotten (threat model T1, T2).

import type {
  GetResponses,
  HistoryEntry,
  HomeData,
  Item,
  LaunchCode,
  NoteDetail,
  NoteSaved,
  NoteSource,
  NoteSummary,
  SaveConflict,
  SaveNote,
  SearchResult,
  TaskSummary,
} from './api-types'

export const CSRF_HEADER = 'X-Onyx-Request'

export class ApiError extends Error {
  readonly status: number
  /** The parsed JSON error body, if there was one (a 409 carries the note's version). */
  readonly body: unknown

  constructor(status: number, message: string, body?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
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
    let body: unknown
    try {
      body = await response.json()
      const detail = (body as { detail?: unknown }).detail
      if (typeof detail === 'string') message = detail
    } catch {
      // not JSON; keep the status text
    }
    throw new ApiError(response.status, message, body)
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
export type { HistoryEntry, HomeData, Item, NoteDetail, NoteSaved, NoteSource, NoteSummary, SaveConflict, SearchResult, TaskSummary }

export async function getHome(): Promise<HomeData> {
  return apiGet('/api/home')
}

export async function getItems(): Promise<Item[]> {
  return (await apiGet('/api/items')).items
}

/** Notes and tasks matching the words in `text`, by title and content, best first. */
export async function search(text: string): Promise<SearchResult[]> {
  return (await apiGet('/api/search', { q: text })).results
}

/** Search starts at this many characters. */
export const SEARCH_MIN_CHARS = 2

export async function getNotes(): Promise<NoteSummary[]> {
  return (await apiGet('/api/notes')).notes
}

export async function getNote(path: string): Promise<NoteDetail> {
  return apiGet('/api/note', { path })
}

/** A note's body as written, for the editor, with its frontmatter (shown, not edited) and version. */
export async function getNoteSource(path: string): Promise<NoteSource> {
  return apiGet('/api/note/source', { path })
}

/**
 * Save a note's body. `version` is the one the editor opened: if the file
 * changed on disk since, the server refuses with a 409 and nothing is written.
 */
export async function saveNote(path: string, body: string, version: string): Promise<NoteSaved> {
  const request: SaveNote = { path, body, version }
  const response = await apiFetch('/api/note', { method: 'PUT', body: JSON.stringify(request) })
  return (await response.json()) as NoteSaved
}

/** The address of the Notes page, optionally showing one folder, one tag or a search. */
export function notesPath(filter: { folder?: string; tag?: string; q?: string } = {}): string {
  if (filter.q !== undefined) return `/notes?q=${encodeURIComponent(filter.q)}`
  if (filter.tag !== undefined) return `/notes?tag=${encodeURIComponent(filter.tag)}`
  if (filter.folder !== undefined) return `/notes?folder=${encodeURIComponent(filter.folder)}`
  return '/notes'
}

/** The address of the focus view for a note or task. */
export function focusPath(path: string): string {
  return `/focus?path=${encodeURIComponent(path)}`
}
