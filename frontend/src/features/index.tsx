import Focus from '../Focus'
import Home from '../Home'
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
    id: 'focus',
    route: { path: '/focus', element: <Focus /> },
    panels: [{ id: 'details', title: 'Details', defaultVisible: true, render: (c) => <DetailsPanel {...c} /> }],
  },
]

const PANEL_ORDER = ['details', 'history']

/** Every registered panel, Details first. */
export const PANELS: PanelDefinition[] = FEATURES.flatMap((f) => f.panels ?? []).sort(
  (a, b) => PANEL_ORDER.indexOf(a.id) - PANEL_ORDER.indexOf(b.id),
)
