import { DropdownMenu } from 'radix-ui'
import { Group, Panel, Separator, useDefaultLayout } from 'react-resizable-panels'
import { useCurrentItem } from './currentItem'
import type { PanelDefinition } from './features/types'

const SEPARATOR =
  'h-1.5 shrink-0 bg-stone-200 outline-none hover:bg-emerald-500/40 focus-visible:bg-emerald-500/60 data-[separator=active]:bg-emerald-500/60 dark:bg-stone-800'

/** The side area: the panels the user picked, stacked and resizable. */
export default function PanelArea({
  panels,
  visible,
  onAdd,
  onRemove,
}: {
  panels: PanelDefinition[]
  visible: string[]
  onAdd: (id: string) => void
  onRemove: (id: string) => void
}) {
  const { item } = useCurrentItem()
  const shown = panels.filter((p) => visible.includes(p.id))
  const hidden = panels.filter((p) => !visible.includes(p.id))
  const sizes = useDefaultLayout({ id: 'onyx-side-panels', panelIds: shown.map((p) => p.id), storage: localStorage })

  return (
    <aside aria-label="Panels" className="flex h-full flex-col border-l border-stone-200 dark:border-stone-800">
      <div className="flex shrink-0 items-center justify-between px-3 py-2">
        <span className="text-xs font-medium tracking-wide text-stone-500 uppercase">Panels</span>
        <DropdownMenu.Root>
          <DropdownMenu.Trigger
            disabled={hidden.length === 0}
            className="rounded px-2 py-0.5 text-sm text-stone-500 hover:bg-stone-200 disabled:opacity-40 dark:hover:bg-stone-800"
          >
            + Add panel
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              className="min-w-40 rounded-lg bg-white p-1 text-sm shadow-lg ring-1 ring-stone-200 dark:bg-stone-900 dark:ring-stone-700"
            >
              {hidden.map((p) => (
                <DropdownMenu.Item
                  key={p.id}
                  onSelect={() => onAdd(p.id)}
                  className="cursor-default rounded px-3 py-1.5 outline-none data-highlighted:bg-stone-100 dark:data-highlighted:bg-stone-800"
                >
                  {p.title}
                </DropdownMenu.Item>
              ))}
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
      {shown.length === 0 ? (
        <p className="px-3 py-2 text-sm text-stone-500">No panels. Add one above.</p>
      ) : (
        <Group
          orientation="vertical"
          className="min-h-0 flex-1"
          defaultLayout={sizes.defaultLayout}
          onLayoutChanged={sizes.onLayoutChanged}
        >
          {shown.map((p, index) => (
            <PanelSlot key={p.id} panel={p} last={index === shown.length - 1} onRemove={onRemove} item={item} />
          ))}
        </Group>
      )}
    </aside>
  )
}

function PanelSlot({
  panel,
  last,
  onRemove,
  item,
}: {
  panel: PanelDefinition
  last: boolean
  onRemove: (id: string) => void
  item: ReturnType<typeof useCurrentItem>['item']
}) {
  return (
    <>
      <Panel id={panel.id} minSize={80} className="flex flex-col">
        <section aria-label={panel.title} className="flex min-h-0 flex-1 flex-col">
          <header className="flex shrink-0 items-center justify-between border-t border-stone-200 px-3 py-1.5 dark:border-stone-800">
            <h2 className="text-sm font-semibold">{panel.title}</h2>
            <button
              type="button"
              onClick={() => onRemove(panel.id)}
              aria-label={`Remove ${panel.title} panel`}
              className="rounded px-1.5 text-stone-500 hover:bg-stone-200 dark:hover:bg-stone-800"
            >
              ×
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-auto px-3 pb-3">{panel.render({ item })}</div>
        </section>
      </Panel>
      {!last && <Separator className={SEPARATOR} />}
    </>
  )
}
