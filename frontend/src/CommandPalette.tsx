import { useQuery } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import { useEffect, useId, useMemo, useState, type KeyboardEvent } from 'react'
import { getItems } from './api'
import { isPaletteShortcut } from './shortcuts'

export type Command = { id: string; label: string; run: () => void }

type Option =
  | { kind: 'command'; key: string; label: string; run: () => void }
  | { kind: 'note' | 'task'; key: string; label: string }

const MAX_RESULTS = 8
const KIND_LABELS = { command: 'Go', note: 'Note', task: 'Task' } as const

export default function CommandPalette({
  open,
  onOpenChange,
  commands,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  commands: Command[]
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const listId = useId()
  // Loaded when the palette first opens, then kept for this visit.
  const items = useQuery({ queryKey: ['items'], queryFn: getItems, enabled: open })

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (!isPaletteShortcut(event)) return
      event.preventDefault()
      onOpenChange(!open)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onOpenChange])

  const options = useMemo<Option[]>(() => {
    const q = query.trim().toLowerCase()
    const matches = (label: string) => q === '' || label.toLowerCase().includes(q)
    const found: Option[] = commands
      .filter((c) => matches(c.label))
      .map((c) => ({ kind: 'command', key: `command:${c.id}`, label: c.label, run: c.run }))
    for (const item of items.data ?? []) {
      if (found.length >= commands.length + MAX_RESULTS) break
      if (matches(item.title)) found.push({ kind: item.kind, key: `${item.kind}:${item.path}`, label: item.title })
    }
    return found
  }, [query, commands, items.data])

  function changeOpen(next: boolean) {
    if (next) {
      setQuery('')
      setActive(0)
    }
    onOpenChange(next)
  }

  function choose(option: Option | undefined) {
    if (!option || option.kind !== 'command') return // notes and tasks open with the focus view (next)
    onOpenChange(false)
    option.run()
  }

  function onInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => (options.length === 0 ? 0 : (i + 1) % options.length))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => (options.length === 0 ? 0 : (i - 1 + options.length) % options.length))
    } else if (event.key === 'Enter') {
      event.preventDefault()
      choose(options[active])
    }
  }

  const activeIndex = Math.min(active, Math.max(options.length - 1, 0))
  const optionId = (index: number) => `${listId}-${index}`

  return (
    <Dialog.Root open={open} onOpenChange={changeOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed top-[15vh] left-1/2 w-[92vw] max-w-lg -translate-x-1/2 overflow-hidden rounded-xl bg-white text-stone-900 shadow-2xl ring-1 ring-stone-200 dark:bg-stone-900 dark:text-stone-100 dark:ring-stone-700"
        >
          <Dialog.Title className="sr-only">Find anything</Dialog.Title>
          <input
            role="combobox"
            aria-label="Search notes, tasks and commands"
            aria-expanded="true"
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={options.length > 0 ? optionId(activeIndex) : undefined}
            placeholder="Search notes, tasks and commands…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setActive(0)
            }}
            onKeyDown={onInputKeyDown}
            maxLength={200}
            className="w-full border-b border-stone-200 bg-transparent px-4 py-3 outline-none dark:border-stone-700"
          />
          <ul id={listId} role="listbox" aria-label="Results" className="max-h-80 overflow-auto p-2">
            {options.map((option, index) => (
              <li
                key={option.key}
                id={optionId(index)}
                role="option"
                aria-selected={index === activeIndex}
                aria-disabled={option.kind !== 'command'}
                onMouseMove={() => setActive(index)}
                onClick={() => choose(option)}
                className={`flex cursor-default items-center gap-2 rounded px-3 py-2 ${index === activeIndex ? 'bg-stone-100 dark:bg-stone-800' : ''} ${option.kind === 'command' ? '' : 'text-stone-500'}`}
              >
                <span className="w-10 shrink-0 text-xs text-stone-500">{KIND_LABELS[option.kind]}</span>
                <span className="truncate">{option.label}</span>
              </li>
            ))}
            {options.length === 0 && <li className="px-3 py-2 text-stone-500">No matches.</li>}
          </ul>
          <p className="border-t border-stone-200 px-4 py-2 text-xs text-stone-500 dark:border-stone-700">
            {items.isError
              ? "Notes and tasks couldn't be loaded."
              : 'Opening notes and tasks comes with the focus view. ↑↓ to move, Enter to choose, Esc to close.'}
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
