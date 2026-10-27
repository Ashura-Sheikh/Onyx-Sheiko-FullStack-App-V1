import { createContext, useContext } from 'react'
import type { NoteDetail } from './api'

export type CurrentItem = { item: NoteDetail | null; setItem: (item: NoteDetail | null) => void }

/** The note or task open in the focus view, shared with the side panels. */
export const CurrentItemContext = createContext<CurrentItem>({ item: null, setItem: () => {} })

export function useCurrentItem(): CurrentItem {
  return useContext(CurrentItemContext)
}
