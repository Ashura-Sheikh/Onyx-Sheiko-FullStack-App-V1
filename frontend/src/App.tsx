import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router'
import { ApiError, getSession, signOut } from './api'
import Frame from './Frame'
import Home from './Home'
import SignIn from './SignIn'
import { applyTheme, initialTheme, saveTheme, type Theme } from './theme'

type State = 'checking' | 'signed-out' | 'signed-in' | 'offline'

function NotFound() {
  return (
    <>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Not here yet</h1>
      <p className="text-stone-500">
        This page doesn't exist yet.{' '}
        <Link to="/" className="underline">
          Back to Home
        </Link>
      </p>
    </>
  )
}

export default function App() {
  const [state, setState] = useState<State>('checking')
  const [theme, setTheme] = useState<Theme>(initialTheme)
  // One client per app: a 401 on any request means the session has ended.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (error) => {
            if (error instanceof ApiError && error.status === 401) setState('signed-out')
          },
        }),
        defaultOptions: { queries: { retry: false, refetchOnWindowFocus: true } },
      }),
  )

  useEffect(() => applyTheme(theme), [theme])

  useEffect(() => {
    getSession()
      .then((signedIn) => setState(signedIn ? 'signed-in' : 'signed-out'))
      .catch(() => setState('offline'))
  }, [])

  // Signed out: drop everything read from the vault from memory.
  useEffect(() => {
    if (state === 'signed-out') queryClient.clear()
  }, [state, queryClient])

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark'
      saveTheme(next)
      return next
    })
  }, [])

  const handleSignOut = useCallback(() => {
    signOut().finally(() => setState('signed-out'))
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
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Frame theme={theme} onToggleTheme={toggleTheme} onSignOut={handleSignOut}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Frame>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
