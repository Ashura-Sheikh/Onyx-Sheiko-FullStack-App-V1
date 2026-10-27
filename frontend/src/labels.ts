import type { Priority, Stage } from './api'

export const STAGES: Stage[] = ['open', 'in-progress', 'in-review', 'done']

export const STAGE_LABELS: Record<Stage, string> = {
  open: 'Open',
  'in-progress': 'In progress',
  'in-review': 'In review',
  done: 'Done',
}

// Complete class names only: Tailwind can't see names built from variables.
export const STAGE_CLASSES: Record<Stage, string> = {
  open: 'bg-stone-200 text-stone-800 dark:bg-stone-800 dark:text-stone-200',
  'in-progress': 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300',
  'in-review': 'bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-300',
  done: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-300',
}

export const PRIORITY_DOT: Record<Priority, string> = {
  high: 'bg-rose-500',
  normal: 'bg-sky-500',
  low: 'bg-stone-400',
}

export const PRIORITY_LABELS: Record<Priority, string> = {
  high: 'High priority',
  normal: 'Normal priority',
  low: 'Low priority',
}

/** "2031-04-16" → "Wednesday 16 April", read as a calendar date (no time zone shift). */
export function longDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, month - 1, day)))
}

/** "2031-04-16" → "16 Apr". */
export function shortDate(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(Date.UTC(year, month - 1, day)),
  )
}

/** An ISO time → "16 Apr, 09:00" in the browser's time zone. */
export function dateTime(iso: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  }).format(new Date(iso))
}

export function greeting(hour: number): string {
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export function isStage(value: string): value is Stage {
  return (STAGES as string[]).includes(value)
}
