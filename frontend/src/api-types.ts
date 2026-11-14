// Generated from openapi.json by scripts/gen-api-types.ts. Don't edit by hand:
// change backend/onyx/models.py, then run `uv run python -m onyx.schema` in
// backend/ and `npm run gen:api` here. A test fails if this file is out of date.

export interface ApiSchemas {
  AppSettings: AppSettings
  CreateNote: CreateNote
  DeleteNote: DeleteNote
  ErrorResponse: ErrorResponse
  HTTPValidationError: HTTPValidationError
  Health: Health
  HistoryEntry: HistoryEntry
  HomeData: HomeData
  Item: Item
  ItemList: ItemList
  LaunchCode: LaunchCode
  MoveRefused: MoveRefused
  MoveTask: MoveTask
  NoteCreated: NoteCreated
  NoteDetail: NoteDetail
  NoteList: NoteList
  NoteRef: NoteRef
  NoteRenamed: NoteRenamed
  NoteSaved: NoteSaved
  NoteSource: NoteSource
  NoteSummary: NoteSummary
  NoteTrashed: NoteTrashed
  ParentRef: ParentRef
  RecentNote: RecentNote
  RenameNote: RenameNote
  SaveConflict: SaveConflict
  SaveNote: SaveNote
  SearchResult: SearchResult
  SearchResults: SearchResults
  SessionStatus: SessionStatus
  SnippetPart: SnippetPart
  StageCounts: StageCounts
  SubtaskCount: SubtaskCount
  TaskBoard: TaskBoard
  TaskCard: TaskCard
  TaskDetail: TaskDetail
  TaskHistoryEntry: TaskHistoryEntry
  TaskMoved: TaskMoved
  TaskRef: TaskRef
  TaskSummary: TaskSummary
  ValidationError: ValidationError
}
export interface AppSettings {
  /**
   * The sign-off name (--identity); null if not set
   */
  identity: string | null
  /**
   * False unless the server was started with --allow-writes
   */
  writable: boolean
}
export interface CreateNote {
  /**
   * An existing folder; "" is the top level
   */
  folder: string
  /**
   * The note's name; .md is added
   */
  name: string
}
export interface DeleteNote {
  path: string
  /**
   * The version that was opened
   */
  version: string
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
export interface MoveRefused {
  detail: string
  /**
   * changed: the note changed on disk since it was opened; exists: a note with the new name is already there
   */
  reason: 'changed' | 'exists'
}
export interface MoveTask {
  path: string
  to: 'open' | 'in-progress' | 'in-review' | 'done'
  /**
   * The version that was opened
   */
  version: string
}
export interface NoteCreated {
  path: string
  version: string
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
export interface NoteRenamed {
  /**
   * The note's new path
   */
  path: string
}
export interface NoteSaved {
  path: string
  version: string
}
export interface NoteSource {
  /**
   * Everything after the frontmatter, as written
   */
  body: string
  /**
   * The frontmatter block as written; shown, not edited
   */
  frontmatter: string
  path: string
  /**
   * SHA-256 of the file; quote it when saving
   */
  version: string
  /**
   * False unless the server was started with --allow-writes
   */
  writable: boolean
}
export interface NoteTrashed {
  /**
   * Where the note went, inside the vault's .trash folder
   */
  trashed_to: string
}
export interface ParentRef {
  path: string
  title: string
}
export interface RenameNote {
  /**
   * The new name, same folder
   */
  name: string
  path: string
  /**
   * The version that was opened
   */
  version: string
}
export interface SaveConflict {
  detail: string
  /**
   * The file's version now (null: it's gone)
   */
  version: string | null
}
export interface SaveNote {
  body: string
  path: string
  /**
   * The version the editor opened
   */
  version: string
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
export interface SubtaskCount {
  done: number
  total: number
}
export interface TaskBoard {
  tasks: TaskCard[]
}
export interface TaskCard {
  /**
   * YYYY-MM-DD
   */
  due: string | null
  /**
   * The parent task, for a task tagged subtask
   */
  parent: ParentRef | null
  path: string
  priority: ('high' | 'normal' | 'low') | null
  /**
   * Project links (not the parent), as written
   */
  projects: string[]
  status: ('open' | 'in-progress' | 'in-review' | 'done') | null
  /**
   * Sub-task progress, for a parent task
   */
  subtasks: SubtaskCount | null
  title: string
}
export interface TaskMoved {
  path: string
  status: 'open' | 'in-progress' | 'in-review' | 'done'
  version: string
}

/** The response type of each GET endpoint. */
export interface GetResponses {
  '/api/app-settings': AppSettings
  '/api/health': Health
  '/api/home': HomeData
  '/api/items': ItemList
  '/api/note': NoteDetail
  '/api/note/source': NoteSource
  '/api/notes': NoteList
  '/api/search': SearchResults
  '/api/session': SessionStatus
  '/api/tasks': TaskBoard
}
