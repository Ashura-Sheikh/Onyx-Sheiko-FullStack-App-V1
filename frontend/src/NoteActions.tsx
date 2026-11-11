// Create, rename and delete notes (part (d) of #8). Notes only: tasks get
// theirs in Tasks (#9). Rename keeps the note in its folder and doesn't change
// [[links]] in other notes; delete moves the note to the vault's .trash folder.

import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { createNote, deleteNote, focusPath, getNote, getNoteSource, notesPath, renameNote, type NoteDetail } from './api'
import { nameOf, writeProblem } from './noteWrites'

const BUTTON = 'rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-900'
const PRIMARY =
  'rounded-lg bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50'
const DANGER =
  'rounded-lg bg-rose-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-rose-800 disabled:cursor-not-allowed disabled:opacity-50'
const INPUT =
  'w-full rounded-lg border border-stone-300 bg-transparent px-3 py-2 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 dark:border-stone-700'

/** Everything that lists or shows notes reads them again. */
async function refreshNotes(queryClient: QueryClient, gone?: string) {
  if (gone !== undefined) queryClient.removeQueries({ queryKey: ['note', gone] })
  await Promise.all([['notes'], ['home'], ['items'], ['search']].map((queryKey) => queryClient.invalidateQueries({ queryKey })))
}

function Shell({ open, onOpenChange, title, children }: { open: boolean; onOpenChange: (open: boolean) => void; title: string; children: ReactNode }) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 text-stone-900 shadow-xl dark:bg-stone-900 dark:text-stone-100">
          <Dialog.Title className="mb-3 text-lg font-semibold">{title}</Dialog.Title>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function Problem({ text }: { text: string | null }) {
  if (!text) return null
  return (
    <p role="alert" className="mb-3 rounded-lg bg-rose-100 px-3 py-2 text-sm text-rose-900 dark:bg-rose-950 dark:text-rose-200">
      {text}
    </p>
  )
}

/** "New note" on the Notes page: an empty note in the folder being shown, opened for editing. */
export function NewNote({ folder }: { folder: string }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  function openChange(next: boolean) {
    setOpen(next)
    if (next) {
      setName('')
      setProblem(null)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || name.trim() === '') return
    setBusy(true)
    setProblem(null)
    try {
      const created = await createNote(folder, name)
      await refreshNotes(queryClient)
      setOpen(false)
      navigate(focusPath(created.path), { state: { edit: true } })
    } catch (error) {
      setProblem(writeProblem(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" className={PRIMARY} onClick={() => openChange(true)}>
        New note
      </button>
      <Shell open={open} onOpenChange={openChange} title="New note">
        <form onSubmit={submit}>
          <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
            An empty note in <strong>{folder || 'the top level'}</strong>, opened for editing.
          </Dialog.Description>
          <label htmlFor="new-note-name" className="mb-1 block text-sm font-medium">
            Name
          </label>
          <input id="new-note-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} autoComplete="off" className={`${INPUT} mb-3`} />
          <Problem text={problem} />
          <div className="flex justify-end gap-2">
            <Dialog.Close className={BUTTON}>Cancel</Dialog.Close>
            <button type="submit" className={PRIMARY} disabled={busy || name.trim() === ''}>
              {busy ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </Shell>
    </>
  )
}

type Fresh = { version: string; writable: boolean; linking: number }

/** The note as it is now: the version to quote, whether writes are on, and how many notes and tasks link to it. */
async function fresh(path: string): Promise<Fresh> {
  const [source, detail] = await Promise.all([getNoteSource(path), getNote(path)])
  return { version: source.version, writable: source.writable, linking: detail.backlinks.length + detail.related_tasks.length }
}

function LinkWarning({ linking, what }: { linking: number; what: 'rename' | 'delete' }) {
  if (linking === 0) return <p className="mb-3 text-sm text-stone-500">No other notes or tasks link to it.</p>
  const count = `${linking} ${linking === 1 ? 'note or task links' : 'notes and tasks link'} to it`
  return (
    <p data-testid="link-warning" className="mb-3 rounded-lg bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">
      {count}. {what === 'rename' ? "Their links won't be updated, so they'll stop working." : "Their links will stop working."}
    </p>
  )
}

const READ_ONLY = 'Read-only: the server was started without --allow-writes, so nothing can be changed.'

/** Rename and Delete in a note's view. Not shown for tasks. */
export function RenameDelete({ item }: { item: NoteDetail }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [dialog, setDialog] = useState<'rename' | 'delete' | null>(null)
  const [state, setState] = useState<Fresh | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  async function start(which: 'rename' | 'delete') {
    setDialog(which)
    setState(null)
    setProblem(null)
    setName(nameOf(item.path))
    try {
      setState(await fresh(item.path))
    } catch (error) {
      setProblem(writeProblem(error))
    }
  }

  function close(open: boolean) {
    if (!open) setDialog(null)
  }

  async function run(action: () => Promise<void>) {
    if (busy || !state?.writable) return
    setBusy(true)
    setProblem(null)
    try {
      await action()
    } catch (error) {
      setProblem(writeProblem(error))
    } finally {
      setBusy(false)
    }
  }

  const doRename = (event: FormEvent) => {
    event.preventDefault()
    if (name.trim() === '' || name.trim() === nameOf(item.path)) return
    void run(async () => {
      const renamed = await renameNote(item.path, name, state!.version)
      await refreshNotes(queryClient, item.path)
      setDialog(null)
      navigate(focusPath(renamed.path), { replace: true })
    })
  }

  const doDelete = () =>
    void run(async () => {
      const trashed = await deleteNote(item.path, state!.version)
      await refreshNotes(queryClient, item.path)
      setDialog(null)
      navigate(notesPath({ folder: item.folder }), { state: { notice: `Moved “${item.title}” to ${trashed.trashed_to}.` } })
    })

  const ready = state !== null
  const unchanged = name.trim() === '' || name.trim() === nameOf(item.path)

  return (
    <>
      <button type="button" className={BUTTON} onClick={() => void start('rename')}>
        Rename
      </button>
      <button type="button" className={BUTTON} onClick={() => void start('delete')}>
        Delete
      </button>

      <Shell open={dialog === 'rename'} onOpenChange={close} title="Rename note">
        <form onSubmit={doRename}>
          <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
            The note stays in <strong>{item.folder || 'the top level'}</strong>.
          </Dialog.Description>
          <label htmlFor="rename-note-name" className="mb-1 block text-sm font-medium">
            New name
          </label>
          <input id="rename-note-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} autoComplete="off" className={`${INPUT} mb-3`} />
          {!ready && !problem && <p className="mb-3 text-sm text-stone-500">Checking links…</p>}
          {state && <LinkWarning linking={state.linking} what="rename" />}
          {state && !state.writable && <p role="status" className="mb-3 text-sm text-amber-800 dark:text-amber-300">{READ_ONLY}</p>}
          <Problem text={problem} />
          <div className="flex justify-end gap-2">
            <Dialog.Close className={BUTTON}>Cancel</Dialog.Close>
            <button type="submit" className={PRIMARY} disabled={busy || !state?.writable || unchanged}>
              {busy ? 'Renaming…' : 'Rename'}
            </button>
          </div>
        </form>
      </Shell>

      <Shell open={dialog === 'delete'} onOpenChange={close} title="Delete note">
        <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
          Move <strong>{item.title}</strong> to the vault's <code>.trash</code> folder? You can get it back from there in Finder or Obsidian.
        </Dialog.Description>
        {!ready && !problem && <p className="mb-3 text-sm text-stone-500">Checking links…</p>}
        {state && <LinkWarning linking={state.linking} what="delete" />}
        {state && !state.writable && <p role="status" className="mb-3 text-sm text-amber-800 dark:text-amber-300">{READ_ONLY}</p>}
        <Problem text={problem} />
        <div className="flex justify-end gap-2">
          <Dialog.Close className={BUTTON}>Cancel</Dialog.Close>
          <button type="button" className={DANGER} onClick={doDelete} disabled={busy || !state?.writable}>
            {busy ? 'Moving…' : 'Move to trash'}
          </button>
        </div>
      </Shell>
    </>
  )
}
