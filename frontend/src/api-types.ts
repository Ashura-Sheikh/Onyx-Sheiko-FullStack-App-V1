// Generated from openapi.json by scripts/gen-api-types.ts. Don't edit by hand:
// change backend/onyx/models.py, then run `uv run python -m onyx.schema` in
// backend/ and `npm run gen:api` here. A test fails if this file is out of date.

export interface ApiSchemas {
  ErrorResponse: ErrorResponse
  HTTPValidationError: HTTPValidationError
  Health: Health
  HistoryEntry: HistoryEntry
  HomeData: HomeData
  Item: Item
  ItemList: ItemList
  LaunchCode: LaunchCode
  NoteDetail: NoteDetail
  NoteList: NoteList
  NoteRef: NoteRef
  NoteSummary: NoteSummary
  RecentNote: RecentNote
  SearchResult: SearchResult
  SearchResults: SearchResults
  SessionStatus: SessionStatus
  SnippetPart: SnippetPart
  StageCounts: StageCounts
  TaskDetail: TaskDetail
  TaskHistoryEntry: TaskHistoryEntry
  TaskRef: TaskRef
  TaskSummary: TaskSummary
  ValidationError: ValidationError
}
export interface ErrorResponse {
  detail: string
}
export interface HTTPValidationError {
  detail?: ValidationError[]
}
export interface ValidationError {
  ctx?: {}
  input?: unknown
  loc: (string | number)[]
  msg: string
  type: string
}
export interface Health {
  status: string
}
export interface HistoryEntry {
  /**
   * ISO 8601 time
   */
  at: string
  from: string
  path: string
  remark: string | null
  title: string
  to: 'open' | 'in-progress' | 'in-review' | 'done'
}
export interface HomeData {
  counts: StageCounts
  due: TaskSummary[]
  history: HistoryEntry[]
  recent_notes: RecentNote[]
  /**
   * YYYY-MM-DD
   */
  today: string
  waiting: TaskSummary[]
}
export interface StageCounts {
  done: number
  'in-progress': number
  'in-review': number
  open: number
}
export interface TaskSummary {
  /**
   * YYYY-MM-DD
   */
  due: string | null
  path: string
  priority: ('high' | 'normal' | 'low') | null
  status: ('open' | 'in-progress' | 'in-review' | 'done') | null
  title: string
}
export interface RecentNote {
  folder: string
  path: string
  title: string
  /**
   * ISO 8601 time
   */
  updated: string
}
export interface Item {
  kind: 'note' | 'task'
  path: string
  title: string
}
export interface ItemList {
  items: Item[]
}
export interface LaunchCode {
  code: string
}
export interface NoteDetail {
  backlinks: NoteRef[]
  body: string
  folder: string
  kind: 'note' | 'task'
  /**
   * Each [[link]] target in the body, and the note it opens (null: none)
   */
  links: {
    [k: string]: string | null
  }
  path: string
  related_tasks: TaskRef[]
  tags: string[]
  task: TaskDetail | null
  title: string
  /**
   * ISO 8601 time
   */
  updated: string
}
export interface NoteRef {
  path: string
  title: string
}
export interface TaskRef {
  path: string
  status: ('open' | 'in-progress' | 'in-review' | 'done') | null
  title: string
}
export interface TaskDetail {
  closed_by: string | null
  completed: string | null
  created: string | null
  /**
   * YYYY-MM-DD
   */
  due: string | null
  history: TaskHistoryEntry[]
  priority: ('high' | 'normal' | 'low') | null
  projects: string[]
  status: ('open' | 'in-progress' | 'in-review' | 'done') | null
  time_to_close_minutes: number | null
}
export interface TaskHistoryEntry {
  /**
   * ISO 8601 time
   */
  at: string
  from: string
  remark: string | null
  to: 'open' | 'in-progress' | 'in-review' | 'done'
}
export interface NoteList {
  notes: NoteSummary[]
}
export interface NoteSummary {
  folder: string
  path: string
  tags: string[]
  title: string
  /**
   * ISO 8601 time
   */
  updated: string
}
export interface SearchResult {
  folder: string
  kind: 'note' | 'task'
  path: string
  /**
   * Body text around the match, matched words marked
   */
  snippet: SnippetPart[]
  title: string
}
export interface SnippetPart {
  match: boolean
  text: string
}
export interface SearchResults {
  results: SearchResult[]
}
export interface SessionStatus {
  authenticated: boolean
}

/** The response type of each GET endpoint. */
export interface GetResponses {
  '/api/health': Health
  '/api/home': HomeData
  '/api/items': ItemList
  '/api/note': NoteDetail
  '/api/notes': NoteList
  '/api/search': SearchResults
  '/api/session': SessionStatus
}
