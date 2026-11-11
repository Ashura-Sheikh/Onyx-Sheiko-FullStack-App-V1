// Moving a task one stage on (#9 part (b)). One stage at a time, forward
// only; done needs a sign-off under the server's --identity. The task is read
// again just before each move, for the version to quote.

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import { useState } from 'react'
import { getAppSettings, getNoteSource, moveTask, type Stage } from './api'
import { STAGE_LABELS } from './labels'
import { moveProblem, NO_IDENTITY_REASON, nextStage, READ_ONLY_REASON } from './taskMoves'

type Movable = { path: string; title: string; status: Stage | null }

const BUTTON =
  'rounded-lg border border-stone-300 px-2.5 py-1 text-xs font-medium hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-stone-700 dark:hover:bg-stone-900'
const PRIMARY =
  'rounded-lg bg-emerald-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50'
const PLAIN = 'rounded-lg border border-stone-300 px-3 py-1.5 text-sm hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-900'

/** "Move to …" for open and in-progress; "Sign off and close…" in review; nothing once done. */
export default function TaskMove({ task }: { task: Movable }) {
  const queryClient = useQueryClient()
  const app = useQuery({ queryKey: ['app-settings'], queryFn: getAppSettings, staleTime: Infinity })
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [confirm, setConfirm] = useState(false)
  const next = nextStage(task.status)
  if (next === null || !app.data) return null
  const settings = app.data
  const blocked = !settings.writable ? READ_ONLY_REASON : next === 'done' && !settings.identity ? NO_IDENTITY_REASON : null

  async function go() {
    if (busy || blocked || next === null) return
    setBusy(true)
    setProblem(null)
    try {
      const source = await getNoteSource(task.path)
      await moveTask(task.path, next, source.version)
      await Promise.all(
        [['tasks'], ['note', task.path], ['home'], ['items']].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
      )
      setConfirm(false)
    } catch (error) {
      setProblem(moveProblem(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-2">
      {next === 'done' ? (
        <button type="button" className={BUTTON} title={blocked ?? undefined} disabled={blocked !== null} onClick={() => setConfirm(true)}>
          Sign off and close…
        </button>
      ) : (
        <button type="button" className={BUTTON} title={blocked ?? undefined} disabled={blocked !== null || busy} onClick={() => void go()}>
          {busy ? 'Moving…' : `Move to ${STAGE_LABELS[next]} →`}
        </button>
      )}
      {blocked && <span className="sr-only">{blocked}</span>}
      {problem && !confirm && (
        <p role="alert" className="mt-1 text-xs text-rose-700 dark:text-rose-400">
          {problem}
        </p>
      )}
      <Dialog.Root open={confirm} onOpenChange={(open) => !busy && setConfirm(open)}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/40" />
          <Dialog.Content className="fixed top-1/2 left-1/2 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 text-stone-900 shadow-xl dark:bg-stone-900 dark:text-stone-100">
            <Dialog.Title className="mb-3 text-lg font-semibold">Sign off and close</Dialog.Title>
            <Dialog.Description className="mb-3 text-sm text-stone-600 dark:text-stone-300">
              Sign off <strong>{task.title}</strong> as <strong>{settings.identity}</strong> and move it to Done? The sign-off is recorded in the task, as Sheiko records it. A done task can't be moved back from here.
            </Dialog.Description>
            {problem && (
              <p role="alert" className="mb-3 rounded-lg bg-rose-100 px-3 py-2 text-sm text-rose-900 dark:bg-rose-950 dark:text-rose-200">
                {problem}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <Dialog.Close className={PLAIN}>Cancel</Dialog.Close>
              <button type="button" className={PRIMARY} disabled={busy} onClick={() => void go()}>
                {busy ? 'Closing…' : 'Sign off and close'}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
