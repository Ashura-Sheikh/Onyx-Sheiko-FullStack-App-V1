import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useDeferredValue, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'
import { ApiError, getNoteSource, saveNote, type NoteDetail, type NoteSource } from './api'
import Markdown from './Markdown'
import { applied, applyFormat, TOOLBAR, type Format } from './markdownFormat'
import { shownBody } from './readView'
import { IS_MAC } from './shortcuts'

/** A browser text box always gives "\n" line endings; compare on that basis. */
const asTyped = (text: string) => text.replace(/\r\n/g, '\n')

type Problem =
  | { kind: 'conflict' }
  | { kind: 'too-large' }
  | { kind: 'gone' }
  | { kind: 'signed-out' }
  | { kind: 'failed'; message: string }

function problemFor(error: unknown): Problem {
  if (!(error instanceof ApiError)) return { kind: 'failed', message: "Saving failed. Is the server still running?" }
  if (error.status === 409) return { kind: 'conflict' }
  if (error.status === 413) return { kind: 'too-large' }
  if (error.status === 404) return { kind: 'gone' }
  if (error.status === 401) return { kind: 'signed-out' }
  return { kind: 'failed', message: error.message }
}

const PROBLEM_TEXT: Record<Problem['kind'], string> = {
  conflict: 'This note changed on disk since you opened it, so nothing was saved.',
  'too-large': 'This note is too large to save (the limit is 1 MiB), so nothing was saved.',
  gone: 'This note is no longer there (moved or deleted?), so nothing was saved.',
  'signed-out': "You've been signed out, so nothing was saved. Copy your text before signing in again.",
  failed: '',
}

const BUTTON = 'rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-900'
const PRIMARY =
  'rounded-lg bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50'

/** Owned by the focus view, so its Read button can ask before leaving too. */
export type Leaving = {
  dirty: boolean
  setDirty: (dirty: boolean) => void
  confirm: boolean
  setConfirm: (confirm: boolean) => void
}

/** What the preview needs from the note as last read: its title, kind and resolved links. */
export type PreviewOf = Pick<NoteDetail, 'title' | 'kind' | 'links'>

type FormProps = { source: NoteSource; note: PreviewOf; leaving: Leaving; onReload: () => void; onClose: () => void }

function Form({ source, note, leaving, onReload, onClose }: FormProps) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState(source.body)
  const [saving, setSaving] = useState(false)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [copied, setCopied] = useState<'yes' | 'failed' | null>(null)
  const dirty = asTyped(draft) !== asTyped(source.body)
  const box = useRef<HTMLTextAreaElement>(null)
  // Where to put the selection once a toolbar edit has been rendered.
  const pendingSelection = useRef<[number, number] | null>(null)
  const previewText = shownBody(useDeferredValue(draft), note.title)

  useLayoutEffect(() => {
    const selection = pendingSelection.current
    if (selection && box.current) {
      pendingSelection.current = null
      box.current.setSelectionRange(selection[0], selection[1])
    }
  }, [draft])

  function update(value: string) {
    setDraft(value)
    leaving.setDirty(asTyped(value) !== asTyped(source.body))
    leaving.setConfirm(false)
  }

  function format(kind: Format) {
    const el = box.current
    if (!el || !source.writable) return
    const edit = applyFormat(el.value, el.selectionStart, el.selectionEnd, kind)
    pendingSelection.current = [edit.selectStart, edit.selectEnd]
    el.focus()
    el.setSelectionRange(edit.start, edit.end)
    // insertText keeps the browser's own undo (⌘Z) working. Where it isn't
    // available (or there's nothing to insert), set the text directly.
    const typed = edit.text !== '' && typeof document.execCommand === 'function' && document.execCommand('insertText', false, edit.text)
    if (!typed) update(applied(el.value, edit))
  }

  // Leaving the page (reload, closing the tab) with unsaved text asks first.
  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  async function save() {
    if (!dirty || saving || !source.writable) return
    setSaving(true)
    setProblem(null)
    setCopied(null)
    try {
      await saveNote(source.path, draft, source.version)
      // Everything that shows this note reads it again.
      await Promise.all(
        [['note', source.path], ['notes'], ['home'], ['items'], ['search']].map((queryKey) =>
          queryClient.invalidateQueries({ queryKey }),
        ),
      )
      onClose()
    } catch (error) {
      setProblem(problemFor(error))
      setSaving(false)
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(draft)
      setCopied('yes')
    } catch {
      setCopied('failed')
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (!(event.metaKey || event.ctrlKey) || event.altKey || event.shiftKey) return
    const key = event.key.toLowerCase()
    if (key === 's') {
      event.preventDefault()
      void save()
      return
    }
    const tool = TOOLBAR.find((t) => t.shortcut === key)
    if (tool) {
      event.preventDefault()
      format(tool.format)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {!source.writable && (
        <p role="status" className="rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
          Read-only: the server was started without <code>--allow-writes</code>, so changes can't be saved.
        </p>
      )}
      {source.frontmatter !== '' && (
        <details className="text-sm text-stone-500">
          <summary className="cursor-pointer">Fields (kept as they are; edit them in Obsidian)</summary>
          <pre data-testid="frontmatter" className="mt-2 overflow-auto rounded-lg bg-stone-100 p-3 font-mono text-xs dark:bg-stone-900">
            {source.frontmatter}
          </pre>
        </details>
      )}
      {/* Side by side when there's room (the main area's own width, not the window's), else stacked. */}
      <div className="@container">
        <div className="grid gap-4 @4xl:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-2">
            <div role="toolbar" aria-label="Formatting" className="flex flex-wrap gap-1">
              {TOOLBAR.map((tool) => (
                <button
                  key={tool.format}
                  type="button"
                  aria-label={tool.label}
                  title={tool.shortcut ? `${tool.label} (${IS_MAC ? '⌘' : 'Ctrl+'}${tool.shortcut.toUpperCase()})` : tool.label}
                  disabled={!source.writable}
                  // Keep the text box's selection: a click would otherwise move focus first.
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => format(tool.format)}
                  className="min-w-8 rounded-md border border-stone-300 px-2 py-1 font-mono text-xs hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-stone-700 dark:hover:bg-stone-900"
                >
                  {tool.symbol}
                </button>
              ))}
            </div>
            <textarea
              ref={box}
              aria-label="Note text"
              value={draft}
              onChange={(e) => update(e.target.value)}
              onKeyDown={onKeyDown}
              readOnly={!source.writable}
              spellCheck
              rows={24}
              className="min-h-[50vh] w-full resize-y rounded-lg border border-stone-300 bg-transparent p-3 font-mono text-sm leading-6 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 dark:border-stone-700"
            />
          </div>
          <section aria-label="Preview" className="min-w-0 rounded-lg border border-dashed border-stone-300 p-4 dark:border-stone-700 @4xl:max-h-[75vh] @4xl:overflow-auto">
            <h2 className="mb-2 text-xs font-medium tracking-wide text-stone-500 uppercase">Preview</h2>
            <div className={note.kind === 'note' ? 'font-serif text-lg leading-8' : undefined}>
              {previewText.trim() === '' ? (
                <p className="text-stone-500">Nothing to show yet.</p>
              ) : (
                <Markdown text={previewText} links={note.links} preview />
              )}
            </div>
          </section>
        </div>
      </div>
      {problem && (
        <div role="alert" className="rounded-lg bg-rose-100 px-3 py-2 text-sm text-rose-900 dark:bg-rose-950 dark:text-rose-200">
          <p>
            {problem.kind === 'failed' ? problem.message : PROBLEM_TEXT[problem.kind]} Your text is still here.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {problem.kind === 'conflict' && (
              <button type="button" className={BUTTON} onClick={onReload}>
                Reload (discard my edit)
              </button>
            )}
            <button type="button" className={BUTTON} onClick={() => void copy()}>
              Copy my text
            </button>
          </div>
        </div>
      )}
      {copied && (
        <p role="status" className="text-sm text-stone-500">
          {copied === 'yes' ? 'Copied.' : "Couldn't copy. Select the text in the box and copy it yourself."}
        </p>
      )}
      {leaving.confirm ? (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span>Discard your unsaved changes?</span>
          <button type="button" className={BUTTON} onClick={onClose}>
            Discard
          </button>
          <button type="button" className={BUTTON} onClick={() => leaving.setConfirm(false)}>
            Keep editing
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <button type="button" className={PRIMARY} onClick={() => void save()} disabled={!dirty || saving || !source.writable}>
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button type="button" className={BUTTON} onClick={() => (dirty ? leaving.setConfirm(true) : onClose())}>
            Cancel
          </button>
          {dirty && <span className="text-sm text-stone-500">Unsaved changes</span>}
        </div>
      )}
    </div>
  )
}

/**
 * Edit a note's body as plain Markdown (part (c) of #8). The frontmatter isn't
 * edited: the server keeps it byte for byte. Saving quotes the version that
 * was opened; if the file changed on disk since, nothing is saved and the
 * text stays on screen.
 */
type EditorProps = { path: string; note: PreviewOf; leaving: Leaving; onClose: () => void }

export default function NoteEditor({ path, note, leaving, onClose }: EditorProps) {
  // Always the file as it is now, never a cached copy.
  const source = useQuery({
    queryKey: ['note-source', path],
    queryFn: () => getNoteSource(path),
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
  })
  if (source.isPending) return <p className="text-stone-500">Loading…</p>
  if (source.isError) {
    return (
      <p role="alert" className="text-rose-700 dark:text-rose-400">
        This note couldn't be opened for editing. Is the server still running?
      </p>
    )
  }
  // A new version (after "Reload") starts a fresh form.
  return (
    <Form
      key={source.data.version}
      source={source.data}
      note={note}
      leaving={leaving}
      onReload={() => {
        leaving.setDirty(false)
        void source.refetch()
      }}
      onClose={onClose}
    />
  )
}
