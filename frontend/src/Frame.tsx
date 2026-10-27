import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { Group, Panel, Separator, useDefaultLayout } from 'react-resizable-panels'
import { NavLink, useNavigate } from 'react-router'
import { focusPath } from './api'
import CommandPalette, { type Command } from './CommandPalette'
import { CurrentItemContext } from './currentItem'
import type { NoteDetail } from './api'
import { FEATURES, PANELS } from './features'
import { loadLayout, saveLayout, type LayoutPrefs } from './layout'
import PanelArea from './PanelArea'
import type { Theme } from './theme'

const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)
const PANEL_IDS = PANELS.map((p) => p.id)
const DEFAULT_PANELS = PANELS.filter((p) => p.defaultVisible).map((p) => p.id)

const TOP_BUTTON = 'rounded-full px-3 py-1.5 text-stone-500 hover:bg-stone-200 dark:hover:bg-stone-800'

/** The app frame: top bar, ⌘K palette, light/dark, then the page and the side area, full window width. */
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
  const [item, setItem] = useState<NoteDetail | null>(null)
  const [layout, setLayout] = useState<LayoutPrefs>(() => loadLayout(PANEL_IDS, DEFAULT_PANELS))
  const navigate = useNavigate()
  const nextTheme = theme === 'dark' ? 'light' : 'dark'
  const sizes = useDefaultLayout({
    id: 'onyx-frame',
    panelIds: layout.sideOpen ? ['main', 'side'] : ['main'],
    storage: localStorage,
  })

  const updateLayout = useCallback((change: (current: LayoutPrefs) => LayoutPrefs) => {
    setLayout((current) => {
      const next = change(current)
      saveLayout(next)
      return next
    })
  }, [])
  const toggleSide = useCallback(() => updateLayout((l) => ({ ...l, sideOpen: !l.sideOpen })), [updateLayout])

  const commands = useMemo<Command[]>(
    () => [
      ...FEATURES.flatMap((f) => (f.nav ? [{ id: `go:${f.id}`, label: f.nav.label, run: () => navigate(f.nav!.to) }] : [])),
      { id: 'theme', label: `Switch to ${nextTheme} mode`, run: onToggleTheme },
      { id: 'side', label: layout.sideOpen ? 'Hide panels' : 'Show panels', run: toggleSide },
      { id: 'sign-out', label: 'Sign out', run: onSignOut },
    ],
    [navigate, nextTheme, onToggleTheme, onSignOut, layout.sideOpen, toggleSide],
  )

  return (
    <CurrentItemContext.Provider value={{ item, setItem }}>
      <div className="flex h-screen flex-col bg-stone-50 text-[15px] text-stone-900 dark:bg-stone-950 dark:text-stone-100">
        <header className="flex shrink-0 items-center gap-2 border-b border-stone-200 px-6 py-3 dark:border-stone-800">
          <span className="mr-3 text-lg font-semibold tracking-tight">Onyx</span>
          <nav aria-label="Main" className="flex gap-1">
            {FEATURES.filter((f) => f.nav).map((f) => (
              <NavLink
                key={f.id}
                to={f.nav!.to}
                end
                className={({ isActive }) =>
                  `rounded-full px-3 py-1.5 ${isActive ? 'bg-stone-200 font-medium dark:bg-stone-800' : 'text-stone-500 hover:bg-stone-200 dark:hover:bg-stone-800'}`
                }
              >
                {f.nav!.label}
              </NavLink>
            ))}
          </nav>
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="ml-auto rounded-full border border-stone-300 px-4 py-1.5 text-stone-500 hover:border-stone-400 dark:border-stone-700 dark:hover:border-stone-500"
          >
            Find anything <kbd className="ml-2 text-[10px]">{IS_MAC ? '⌘K' : 'Ctrl+K'}</kbd>
          </button>
          <button type="button" onClick={toggleSide} aria-pressed={layout.sideOpen} className={TOP_BUTTON}>
            Panels
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
          <button type="button" onClick={onSignOut} className={TOP_BUTTON}>
            Sign out
          </button>
        </header>

        <Group
          orientation="horizontal"
          className="min-h-0 flex-1"
          defaultLayout={sizes.defaultLayout}
          onLayoutChanged={sizes.onLayoutChanged}
        >
          <Panel id="main" minSize="40%">
            <main className="h-full overflow-auto px-6 py-6 lg:px-10">{children}</main>
          </Panel>
          {layout.sideOpen && (
            <>
              <Separator className="w-1.5 shrink-0 bg-stone-200 outline-none hover:bg-emerald-500/40 focus-visible:bg-emerald-500/60 dark:bg-stone-800" />
              <Panel id="side" defaultSize="25%" minSize={220} maxSize="50%">
                <PanelArea
                  panels={PANELS}
                  visible={layout.visible}
                  onAdd={(id) => updateLayout((l) => ({ ...l, visible: PANEL_IDS.filter((p) => p === id || l.visible.includes(p)) }))}
                  onRemove={(id) => updateLayout((l) => ({ ...l, visible: l.visible.filter((p) => p !== id) }))}
                />
              </Panel>
            </>
          )}
        </Group>
        <CommandPalette
          open={paletteOpen}
          onOpenChange={setPaletteOpen}
          commands={commands}
          onOpenItem={(path) => navigate(focusPath(path))}
        />
      </div>
    </CurrentItemContext.Provider>
  )
}
