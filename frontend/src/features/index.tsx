import Focus from '../Focus'
import Home from '../Home'
import Notes from '../Notes'
import { BacklinksPanel, RelatedTasksPanel, TagsPanel } from './notePanels'
import { DetailsPanel, HistoryPanel } from './panels'
import type { Feature, PanelDefinition } from './types'

/**
 * Every feature in the app. Notes (#8) and Tasks (#9) add themselves here,
 * with their routes, navigation entries and panels.
 */
export const FEATURES: Feature[] = [
  {
    id: 'home',
    route: { path: '/', element: <Home /> },
    nav: { label: 'Home', to: '/' },
    panels: [{ id: 'history', title: 'History', defaultVisible: true, render: (c) => <HistoryPanel {...c} /> }],
  },
  {
    id: 'notes',
    route: { path: '/notes', element: <Notes /> },
    nav: { label: 'Notes', to: '/notes' },
    panels: [
      { id: 'backlinks', title: 'Backlinks', defaultVisible: true, render: (c) => <BacklinksPanel {...c} /> },
      { id: 'related-tasks', title: 'Related tasks', defaultVisible: true, render: (c) => <RelatedTasksPanel {...c} /> },
      { id: 'tags', title: 'Tags', defaultVisible: false, render: () => <TagsPanel /> },
    ],
  },
  {
    id: 'focus',
    route: { path: '/focus', element: <Focus /> },
    panels: [{ id: 'details', title: 'Details', defaultVisible: true, render: (c) => <DetailsPanel {...c} /> }],
  },
]

const PANEL_ORDER = ['details', 'backlinks', 'related-tasks', 'history', 'tags']

/** Every registered panel, Details first. */
export const PANELS: PanelDefinition[] = FEATURES.flatMap((f) => f.panels ?? []).sort(
  (a, b) => PANEL_ORDER.indexOf(a.id) - PANEL_ORDER.indexOf(b.id),
)
