import type { ReactNode } from 'react'
import type { NoteDetail } from '../api'

/** What the panels can see: the note or task open in the focus view, if any. */
export type PanelContext = { item: NoteDetail | null }

export type PanelDefinition = {
  /** Stable id: saved in this browser's layout, so never rename one. */
  id: string
  title: string
  /** Shown the first time, before the user has chosen panels. */
  defaultVisible: boolean
  render: (context: PanelContext) => ReactNode
}

/**
 * A feature plugs into the app by listing its route, its navigation entry
 * and its panels here. The frame and the side area read only this, so a new
 * feature never needs a change to the layout code.
 */
export type Feature = {
  id: string
  route: { path: string; element: ReactNode }
  nav?: { label: string; to: string }
  panels?: PanelDefinition[]
}
