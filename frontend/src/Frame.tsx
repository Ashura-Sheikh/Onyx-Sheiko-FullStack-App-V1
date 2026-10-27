import { useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import CommandPalette, { type Command } from './CommandPalette'
import type { Theme } from './theme'

const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

/** The app frame from mockup C: top bar, ⌘K palette, light/dark, then the page. */
export default function Frame({
  theme,
  onToggleTheme,
  onSignOut,
  children,
}: {
  theme: Theme
  onToggleTheme: () => void
  onSignOut: () => void
  children: ReactNode
}) {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const navigate = useNavigate()
  const nextTheme = theme === 'dark' ? 'light' : 'dark'

  const commands = useMemo<Command[]>(
    () => [
      { id: 'home', label: 'Home', run: () => navigate('/') },
      { id: 'theme', label: `Switch to ${nextTheme} mode`, run: onToggleTheme },
      { id: 'sign-out', label: 'Sign out', run: onSignOut },
    ],
    [navigate, nextTheme, onToggleTheme, onSignOut],
  )

  return (
    <div className="min-h-screen bg-stone-50 text-[15px] text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      <header className="mx-auto flex max-w-5xl items-center gap-2 px-6 py-5">
        <Link to="/" className="rounded text-lg font-semibold tracking-tight">
          Onyx
        </Link>
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="ml-auto rounded-full border border-stone-300 px-4 py-1.5 text-stone-500 hover:border-stone-400 dark:border-stone-700 dark:hover:border-stone-500"
        >
          Find anything <kbd className="ml-2 text-[10px]">{IS_MAC ? '⌘K' : 'Ctrl+K'}</kbd>
        </button>
        <button
          type="button"
          onClick={onToggleTheme}
          aria-label={`Switch to ${nextTheme} mode`}
          title={`Switch to ${nextTheme} mode`}
          className="rounded-full px-2.5 py-1.5 hover:bg-stone-200 dark:hover:bg-stone-800"
        >
          <span aria-hidden="true">◐</span>
        </button>
        <button
          type="button"
          onClick={onSignOut}
          className="rounded-full px-3 py-1.5 text-stone-500 hover:bg-stone-200 dark:hover:bg-stone-800"
        >
          Sign out
        </button>
      </header>
      <main className="mx-auto max-w-5xl px-6 pb-16">{children}</main>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} commands={commands} />
    </div>
  )
}
