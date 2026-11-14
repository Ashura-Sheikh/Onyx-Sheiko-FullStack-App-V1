// Create tasks; Edit details, Rename and Delete in a task's page (#9 part (c)).
// Sub-tasks are the task's checklist lines (Checklist.tsx). The server decides
// every rule; these dialogs only explain.

import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { createTask, deleteTask, editTaskDetails, focusPath, getAppSettings, getNoteSource, renameTask, type NoteDetail, type Priority } from './api'
import { PRIORITY_LABELS } from './labels'
import { BUTTON, DANGER, INPUT, PRIMARY, Problem, READ_ONLY, Shell } from './NoteActions'
import { nameOf } from './noteWrites'
import { splitList, taskProblem } from './taskWrites'
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

function ReadOnly({ writable }: { writable: boolean | undefined }) {
  if (writable !== false) return null
  return (
    <p role="status" className="mb-3 text-sm text-amber-800 dark:text-amber-300">
      {READ_ONLY}
    </p>
  )
}

function PrioritySelect({ value, onChange }: { value: Priority | ''; onChange: (value: Priority | '') => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as Priority | '')} className={`${INPUT} mt-1`}>
      <option value="">None</option>
      {(['high', 'normal', 'low'] as Priority[]).map((p) => (
        <option key={p} value={p}>
          {PRIORITY_LABELS[p].replace(' priority', '')}
        </option>
      ))}
    </select>
  )
}

const DESCRIPTION_HINT = 'Markdown. Sub-tasks are added on the task’s page.'

/** "New task" on the Tasks page. */
export function NewTask() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const writable = useWritable()
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<Priority | ''>('')
  const [due, setDue] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  function openChange(next: boolean) {
    setOpen(next)
    if (next) {
      setTitle('')
      setPriority('')
      setDue('')
      setDescription('')
      setProblem(null)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !writable || title.trim() === '') return
    setBusy(true)
    setProblem(null)
    try {
      const created = await createTask({ title, priority: priority || null, due: due || null, description })
      await refreshTasks(queryClient)
      setOpen(false)
      navigate(focusPath(created.path))
    } catch (error) {
      setProblem(taskProblem(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" className={PRIMARY} onClick={() => openChange(true)}>
        New task
      </button>
      <Shell open={open} onOpenChange={openChange} title="New task">
        <form onSubmit={submit}>
          <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">A new task in the Tasks folder, starting Open.</Dialog.Description>
          <label htmlFor="new-task-title" className="mb-1 block text-sm font-medium">
            Title
          </label>
          <input id="new-task-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} autoComplete="off" className={`${INPUT} mb-3`} />
          <div className="mb-3 grid grid-cols-2 gap-3">
            <label className="text-sm font-medium">
              Priority
              <PrioritySelect value={priority} onChange={setPriority} />
            </label>
            <label className="text-sm font-medium">
              Due
              <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={`${INPUT} mt-1`} />
            </label>
          </div>
          <label className="mb-3 block text-sm font-medium">
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} maxLength={20000} className={`${INPUT} mt-1 font-normal`} />
            <span className="text-xs font-normal text-stone-500">{DESCRIPTION_HINT}</span>
          </label>
          <ReadOnly writable={writable} />
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

type Dialogs = 'details' | 'rename' | 'delete' | null
type Details = { priority: Priority | ''; due: string; projects: string; tags: string; description: string }

function detailsOf(item: NoteDetail): Details {
  const task = item.task!
  return {
    priority: task.priority ?? '',
    due: task.due ?? '',
    projects: task.projects.join(', '),
    tags: item.tags.join(', '),
    description: task.description,
  }
}

/** In a task's page: Edit details, Rename, Delete. */
export function TaskTools({ item }: { item: NoteDetail }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const writable = useWritable()
  const [dialog, setDialog] = useState<Dialogs>(null)
  const [version, setVersion] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [form, setForm] = useState<Details>(() => detailsOf(item))
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  async function start(which: Exclude<Dialogs, null>) {
    setDialog(which)
    setVersion(null)
    setProblem(null)
    setName(nameOf(item.path))
    setForm(detailsOf(item))
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
    } finally {
      setBusy(false)
    }
  }

  const set = (change: Partial<Details>) => setForm((current) => ({ ...current, ...change }))

  const doDetails = (event: FormEvent) => {
    event.preventDefault()
    void run(async (v) => {
      await editTaskDetails({
        path: item.path,
        version: v,
        priority: form.priority || null,
        due: form.due || null,
        projects: splitList(form.projects),
        tags: splitList(form.tags),
        description: form.description,
      })
      await refreshTasks(queryClient)
      setDialog(null)
    })
  }

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

  const close = (open: boolean) => !open && !busy && setDialog(null)
  const unchanged = name.trim() === '' || name.trim() === nameOf(item.path)

  return (
    <>
      <button type="button" className={BUTTON} onClick={() => void start('details')}>
        Edit details
      </button>
      <button type="button" className={BUTTON} onClick={() => void start('rename')}>
        Rename
      </button>
      <button type="button" className={BUTTON} onClick={() => void start('delete')}>
        Delete
      </button>

      <Shell open={dialog === 'details'} onOpenChange={close} title="Edit details">
        <form onSubmit={doDetails}>
          <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
            The title is the file name: change it with Rename. Only fields you change are written.
          </Dialog.Description>
          <div className="mb-3 grid grid-cols-2 gap-3">
            <label className="text-sm font-medium">
              Priority
              <PrioritySelect value={form.priority} onChange={(priority) => set({ priority })} />
            </label>
            <label className="text-sm font-medium">
              Due
              <input type="date" value={form.due} onChange={(e) => set({ due: e.target.value })} className={`${INPUT} mt-1`} />
            </label>
          </div>
          <label className="mb-3 block text-sm font-medium">
            Projects
            <input value={form.projects} onChange={(e) => set({ projects: e.target.value })} autoComplete="off" className={`${INPUT} mt-1 font-normal`} />
            <span className="text-xs font-normal text-stone-500">Note names, separated by commas. Each becomes a [[link]].</span>
          </label>
          <label className="mb-3 block text-sm font-medium">
            Tags
            <input value={form.tags} onChange={(e) => set({ tags: e.target.value })} autoComplete="off" className={`${INPUT} mt-1 font-normal`} />
            <span className="text-xs font-normal text-stone-500">Separated by commas, without #.</span>
          </label>
          <label className="mb-3 block text-sm font-medium">
            Description
            <textarea value={form.description} onChange={(e) => set({ description: e.target.value })} rows={5} maxLength={20000} className={`${INPUT} mt-1 font-normal`} />
            <span className="text-xs font-normal text-stone-500">{DESCRIPTION_HINT}</span>
          </label>
          <ReadOnly writable={writable} />
          <Problem text={problem} />
          <div className="flex justify-end gap-2">
            <Dialog.Close className={BUTTON}>Cancel</Dialog.Close>
            <button type="submit" className={PRIMARY} disabled={busy || !version || !writable}>
              {busy ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </form>
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
          <ReadOnly writable={writable} />
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
        <ReadOnly writable={writable} />
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
