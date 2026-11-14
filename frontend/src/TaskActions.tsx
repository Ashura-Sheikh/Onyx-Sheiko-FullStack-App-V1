// Create tasks and sub-tasks, make sub-tasks from a checklist, rename and
// delete tasks (#9 part (c)). The server decides; these dialogs only explain.

import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import {
  createTask,
  deleteTask,
  focusPath,
  getAppSettings,
  getNoteSource,
  getTasks,
  makeSubtasks,
  renameTask,
  type NoteDetail,
  type Priority,
} from './api'
import { PRIORITY_LABELS } from './labels'
import { BUTTON, DANGER, INPUT, PRIMARY, Problem, READ_ONLY, Shell } from './NoteActions'
import { nameOf } from './noteWrites'
import { hasSubtasksReason, noSubtasksReason, parentChoices, taskProblem } from './taskWrites'
import { tasksPath } from './tasksView'

async function refreshTasks(queryClient: QueryClient, gone?: string) {
  if (gone !== undefined) queryClient.removeQueries({ queryKey: ['note', gone] })
  await Promise.all(
    [['tasks'], ['notes'], ['home'], ['items'], ['search'], ['note']].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
  )
}

function useWritable(): boolean | undefined {
  return useQuery({ queryKey: ['app-settings'], queryFn: getAppSettings, staleTime: Infinity }).data?.writable
}

/** "New task" (on Tasks), or "New sub-task" (in a task) with the parent fixed. */
export function NewTask({ parent }: { parent?: { path: string; title: string } }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const writable = useWritable()
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: getTasks })
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const [due, setDue] = useState('')
  const [parentPath, setParentPath] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  function openChange(next: boolean) {
    setOpen(next)
    if (next) {
      setTitle('')
      setPriority('')
      setDue('')
      setParentPath(parent?.path ?? '')
      setProblem(null)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !writable || title.trim() === '') return
    setBusy(true)
    setProblem(null)
    try {
      const created = await createTask({
        title,
        priority: priority || null,
        due: due || null,
        parent: parentPath || null,
      })
      await refreshTasks(queryClient)
      setOpen(false)
      navigate(focusPath(created.path))
    } catch (error) {
      setProblem(taskProblem(error))
    } finally {
      setBusy(false)
    }
  }

  const label = parent ? 'New sub-task' : 'New task'
  return (
    <>
      <button type="button" className={parent ? BUTTON : PRIMARY} onClick={() => openChange(true)}>
        {label}
      </button>
      <Shell open={open} onOpenChange={openChange} title={label}>
        <form onSubmit={submit}>
          <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
            {parent ? (
              <>
                A sub-task of <strong>{parent.title}</strong>, in the Tasks folder, starting Open.
              </>
            ) : (
              'A new task in the Tasks folder, starting Open.'
            )}
          </Dialog.Description>
          <label htmlFor="new-task-title" className="mb-1 block text-sm font-medium">
            Title
          </label>
          <input id="new-task-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} autoComplete="off" className={`${INPUT} mb-3`} />
          <div className="mb-3 grid grid-cols-2 gap-3">
            <label className="text-sm font-medium">
              Priority
              <select value={priority} onChange={(e) => setPriority(e.target.value as Priority | '')} className={`${INPUT} mt-1`}>
                <option value="">None</option>
                {(['high', 'normal', 'low'] as Priority[]).map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABELS[p].replace(' priority', '')}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm font-medium">
              Due
              <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={`${INPUT} mt-1`} />
            </label>
          </div>
          {!parent && (
            <label className="mb-3 block text-sm font-medium">
              Sub-task of
              <select value={parentPath} onChange={(e) => setParentPath(e.target.value)} className={`${INPUT} mt-1`}>
                <option value="">Nothing (a task of its own)</option>
                {parentChoices(tasks.data ?? []).map((t) => (
                  <option key={t.path} value={t.path}>
                    {t.title}
                  </option>
                ))}
              </select>
            </label>
          )}
          {writable === false && (
            <p role="status" className="mb-3 text-sm text-amber-800 dark:text-amber-300">
              {READ_ONLY}
            </p>
          )}
          <Problem text={problem} />
          <div className="flex justify-end gap-2">
            <Dialog.Close className={BUTTON}>Cancel</Dialog.Close>
            <button type="submit" className={PRIMARY} disabled={busy || !writable || title.trim() === ''}>
              {busy ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </Shell>
    </>
  )
}

type Dialogs = 'subtasks' | 'rename' | 'delete' | null

/** In a task's view: New sub-task, Make sub-tasks, Rename, Delete. */
export function TaskTools({ item }: { item: NoteDetail }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const writable = useWritable()
  const tasks = useQuery({ queryKey: ['tasks'], queryFn: getTasks })
  const card = tasks.data?.find((t) => t.path === item.path)
  const [dialog, setDialog] = useState<Dialogs>(null)
  const [version, setVersion] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [made, setMade] = useState<{ created: number; skipped: number } | null>(null)

  if (!card) return null
  const noSubtasks = noSubtasksReason(card)
  const blocked = { rename: hasSubtasksReason(card, 'rename'), delete: hasSubtasksReason(card, 'delete') }

  async function start(which: Exclude<Dialogs, null>) {
    setDialog(which)
    setVersion(null)
    setProblem(null)
    setMade(null)
    setName(nameOf(item.path))
    try {
      setVersion((await getNoteSource(item.path)).version)
    } catch (error) {
      setProblem(taskProblem(error))
    }
  }

  async function run(action: (version: string) => Promise<void>) {
    if (busy || !version || !writable) return
    setBusy(true)
    setProblem(null)
    try {
      await action(version)
    } catch (error) {
      setProblem(taskProblem(error))
      await refreshTasks(queryClient) // a partly-done run still made some
    } finally {
      setBusy(false)
    }
  }

  const doSubtasks = () =>
    void run(async (v) => {
      const result = await makeSubtasks(item.path, v)
      await refreshTasks(queryClient)
      setMade({ created: result.created.length, skipped: result.skipped.length })
    })

  const doRename = (event: FormEvent) => {
    event.preventDefault()
    if (name.trim() === '' || name.trim() === nameOf(item.path)) return
    void run(async (v) => {
      const renamed = await renameTask(item.path, name, v)
      await refreshTasks(queryClient, item.path)
      setDialog(null)
      navigate(focusPath(renamed.path), { replace: true })
    })
  }

  const doDelete = () =>
    void run(async (v) => {
      await deleteTask(item.path, v)
      await refreshTasks(queryClient, item.path)
      setDialog(null)
      navigate(tasksPath({ view: 'board' }))
    })

  const readOnly = writable === false && (
    <p role="status" className="mb-3 text-sm text-amber-800 dark:text-amber-300">
      {READ_ONLY}
    </p>
  )
  const close = (open: boolean) => !open && !busy && setDialog(null)
  const unchanged = name.trim() === '' || name.trim() === nameOf(item.path)

  return (
    <>
      {noSubtasks === null && <NewTask parent={{ path: item.path, title: item.title }} />}
      {noSubtasks === null && (
        <button type="button" className={BUTTON} onClick={() => void start('subtasks')}>
          Make sub-tasks…
        </button>
      )}
      <button type="button" className={BUTTON} onClick={() => void start('rename')} disabled={blocked.rename !== null} title={blocked.rename ?? undefined}>
        Rename
      </button>
      <button type="button" className={BUTTON} onClick={() => void start('delete')} disabled={blocked.delete !== null} title={blocked.delete ?? undefined}>
        Delete
      </button>
      {blocked.delete && <span className="sr-only">{blocked.delete}</span>}

      <Shell open={dialog === 'subtasks'} onOpenChange={close} title="Make sub-tasks">
        <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
          Make one sub-task of <strong>{item.title}</strong> for each unticked checklist line (<code>- [ ]</code>) in it. Lines that already have their sub-task are skipped.
          The task itself isn’t changed.
        </Dialog.Description>
        {made && (
          <p role="status" className="mb-3 rounded-lg bg-emerald-100 px-3 py-2 text-sm text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
            Made {made.created} sub-task{made.created === 1 ? '' : 's'}
            {made.skipped > 0 && `; ${made.skipped} already there`}.
          </p>
        )}
        {readOnly}
        <Problem text={problem} />
        <div className="flex justify-end gap-2">
          <Dialog.Close className={BUTTON}>{made ? 'Done' : 'Cancel'}</Dialog.Close>
          {!made && (
            <button type="button" className={PRIMARY} onClick={doSubtasks} disabled={busy || !version || !writable}>
              {busy ? 'Making…' : 'Make sub-tasks'}
            </button>
          )}
        </div>
      </Shell>

      <Shell open={dialog === 'rename'} onOpenChange={close} title="Rename task">
        <form onSubmit={doRename}>
          <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
            The task stays in <strong>{item.folder || 'the top level'}</strong>. Links to it in other notes aren’t updated.
          </Dialog.Description>
          <label htmlFor="rename-task-name" className="mb-1 block text-sm font-medium">
            New name
          </label>
          <input id="rename-task-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} autoComplete="off" className={`${INPUT} mb-3`} />
          {readOnly}
          <Problem text={problem} />
          <div className="flex justify-end gap-2">
            <Dialog.Close className={BUTTON}>Cancel</Dialog.Close>
            <button type="submit" className={PRIMARY} disabled={busy || !version || !writable || unchanged}>
              {busy ? 'Renaming…' : 'Rename'}
            </button>
          </div>
        </form>
      </Shell>

      <Shell open={dialog === 'delete'} onOpenChange={close} title="Delete task">
        <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
          Move <strong>{item.title}</strong> to the vault's <code>.trash</code> folder? You can get it back from there in Finder or Obsidian.
        </Dialog.Description>
        {readOnly}
        <Problem text={problem} />
        <div className="flex justify-end gap-2">
          <Dialog.Close className={BUTTON}>Cancel</Dialog.Close>
          <button type="button" className={DANGER} onClick={doDelete} disabled={busy || !version || !writable}>
            {busy ? 'Moving…' : 'Move to trash'}
          </button>
        </div>
      </Shell>
    </>
  )
}
