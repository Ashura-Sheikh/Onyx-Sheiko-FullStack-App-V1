import { useState, type FormEvent } from 'react'
import { Dialog } from 'radix-ui'
import { ApiError, signIn } from './api'

export default function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(code.trim())
      setCode('')
      onSignedIn()
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? 'That code is wrong, already used or expired. Restart the server for a new one.'
          : 'Sign-in failed. Is the server still running?',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-stone-50 p-6 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl bg-white p-8 shadow-sm ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-800"
      >
        <h1 className="mb-1 text-2xl font-semibold tracking-tight">Onyx Sheiko</h1>
        <p className="mb-6 text-sm text-stone-500">Sign in with the launch code from your terminal.</p>

        <label htmlFor="launch-code" className="mb-1 block text-sm font-medium">
          Launch code
        </label>
        <input
          id="launch-code"
          name="launch-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          required
          maxLength={128}
          className="mb-4 w-full rounded-lg border border-stone-300 bg-transparent px-3 py-2 font-mono text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-600/20 dark:border-stone-700"
        />

        {error && (
          <p role="alert" className="mb-4 text-sm text-rose-700 dark:text-rose-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy || code.trim() === ''}
          className="w-full rounded-full bg-stone-900 py-2 font-medium text-white hover:bg-stone-700 disabled:opacity-50 dark:bg-stone-100 dark:text-stone-900"
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        <Dialog.Root>
          <Dialog.Trigger className="mt-4 w-full text-center text-sm text-stone-500 underline decoration-dotted hover:text-stone-800 dark:hover:text-stone-200">
            Where do I find the code?
          </Dialog.Trigger>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/40" />
            <Dialog.Content className="fixed top-1/2 left-1/2 w-[90vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white p-6 text-stone-900 shadow-xl dark:bg-stone-900 dark:text-stone-100">
              <Dialog.Title className="mb-2 text-lg font-semibold">Your launch code</Dialog.Title>
              <Dialog.Description className="mb-4 text-sm text-stone-600 dark:text-stone-300">
                When the server starts, it prints a one-time launch code in the terminal. It works
                once, for 10 minutes. If it has expired or been used, stop the server and start it
                again for a new one.
              </Dialog.Description>
              <Dialog.Close className="rounded-full bg-stone-900 px-4 py-1.5 text-sm text-white dark:bg-stone-100 dark:text-stone-900">
                Got it
              </Dialog.Close>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      </form>
    </main>
  )
}
