import { useEffect, useState } from 'react'
import { getSession, signOut } from './api'
import SignIn from './SignIn'

type State = 'checking' | 'signed-out' | 'signed-in' | 'offline'

// The app frame, Home, panels and features arrive in the next #7 pull requests.
export default function App() {
  const [state, setState] = useState<State>('checking')

  useEffect(() => {
    getSession()
      .then((signedIn) => setState(signedIn ? 'signed-in' : 'signed-out'))
      .catch(() => setState('offline'))
  }, [])

  if (state === 'checking') {
    return <p className="p-8 text-stone-500">Loading…</p>
  }
  if (state === 'offline') {
    return (
      <p role="alert" className="p-8 text-rose-700">
        Can't reach the Onyx server. Start it with <code>python -m onyx --vault PATH</code>.
      </p>
    )
  }
  if (state === 'signed-out') {
    return <SignIn onSignedIn={() => setState('signed-in')} />
  }
  return (
    <main className="min-h-screen bg-stone-50 p-8 text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Onyx Sheiko</h1>
      <p className="mb-6 text-stone-500">You're signed in. Home and the panels come next.</p>
      <button
        type="button"
        onClick={() => signOut().finally(() => setState('signed-out'))}
        className="rounded-full border border-stone-300 px-4 py-1.5 hover:bg-stone-100 dark:border-stone-700 dark:hover:bg-stone-800"
      >
        Sign out
      </button>
    </main>
  )
}
