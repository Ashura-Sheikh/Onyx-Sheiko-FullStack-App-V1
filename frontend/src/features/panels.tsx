import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { getHome, notesPath } from '../api'
import HistoryList from '../HistoryList'
import { dateTime, duration, PRIORITY_LABELS, shortDate, STAGE_LABELS } from '../labels'
import type { PanelContext } from './types'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1">
      <dt className="shrink-0 text-stone-500">{label}</dt>
      <dd className="min-w-0 text-right break-words">{children}</dd>
    </div>
  )
}

const NOT_RECORDED = <span className="text-stone-500">not recorded</span>

/** Details of the open note or task (mockup A's inspector; the old app's Task Details fields). */
export function DetailsPanel({ item }: PanelContext) {
  if (!item) return <p className="text-sm text-stone-500">Open a note or task to see its details.</p>
  const task = item.task
  return (
    <dl className="text-sm">
      <Row label="Folder">{item.folder || 'Top level'}</Row>
      <Row label="Updated">{dateTime(item.updated)}</Row>
      {task && (
        <>
          <Row label="Stage">{task.status ? STAGE_LABELS[task.status] : NOT_RECORDED}</Row>
          <Row label="Priority">{task.priority ? PRIORITY_LABELS[task.priority] : NOT_RECORDED}</Row>
          <Row label="Due">{task.due ? shortDate(task.due) : 'none'}</Row>
          {task.projects.length > 0 && <Row label="Projects">{task.projects.join(', ')}</Row>}
          <Row label="Opened">{task.created ? dateTime(task.created) : NOT_RECORDED}</Row>
          <Row label="Closed">{task.completed ? dateTime(task.completed) : 'still open'}</Row>
          {task.closed_by && <Row label="Closed by">{task.closed_by}</Row>}
          {task.time_to_close_minutes !== null && <Row label="Open → closed">{duration(task.time_to_close_minutes)}</Row>}
        </>
      )}
      <Row label="Tags">
        {item.tags.length > 0
          ? item.tags.map((t) => (
              <Link key={t} to={notesPath({ tag: t })} className="ml-1 hover:underline">
                #{t}
              </Link>
            ))
          : 'none'}
      </Row>
    </dl>
  )
}

function VaultHistory() {
  const home = useQuery({ queryKey: ['home'], queryFn: getHome })
  if (home.isPending) return <p className="text-sm text-stone-500">Loading…</p>
  if (home.isError) return <p className="text-sm text-rose-700 dark:text-rose-400">History couldn't be loaded.</p>
  return (
    <>
      <p className="mb-1 text-xs text-stone-500">Latest stage changes across your tasks, newest first.</p>
      <HistoryList entries={home.data.history} empty="No stage changes recorded yet." />
    </>
  )
}

/** The open task's own Status History; on any other page, the latest changes across all tasks. */
export function HistoryPanel({ item }: PanelContext) {
  if (!item) return <VaultHistory />
  if (!item.task) return <p className="text-sm text-stone-500">Notes have no stage history.</p>
  const newestFirst = [...item.task.history].reverse()
  return <HistoryList entries={newestFirst} empty="No stage changes recorded yet." />
}
