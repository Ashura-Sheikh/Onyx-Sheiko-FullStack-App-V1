import type { HistoryEntry } from './api'
import { dateTime, isStage, STAGE_LABELS } from './labels'
import { StagePill } from './StagePill'

type Entry = Pick<HistoryEntry, 'at' | 'from' | 'to' | 'remark'> & { title?: string }

/** Stage changes, newest first as given. Titles are shown when the list spans several tasks. */
export default function HistoryList({ entries, empty }: { entries: Entry[]; empty: string }) {
  if (entries.length === 0) return <p className="py-2 text-sm text-stone-500">{empty}</p>
  return (
    <ol className="divide-y divide-stone-200 dark:divide-stone-800">
      {entries.map((entry, index) => {
        const from = isStage(entry.from) ? STAGE_LABELS[entry.from] : entry.from
        return (
          // A task can repeat the same line, so the position is part of the key.
          <li key={`${index}|${entry.at}`} className="py-2 text-sm">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <time dateTime={entry.at} className="text-xs text-stone-500 tabular-nums">
                {dateTime(entry.at)}
              </time>
              <span className="flex items-center gap-1.5 text-xs text-stone-500">
                {from} →
                <StagePill stage={entry.to} />
              </span>
            </div>
            {entry.title && <div className="mt-0.5 truncate">{entry.title}</div>}
            {entry.remark && <div className="mt-0.5 text-xs text-stone-500">{entry.remark}</div>}
          </li>
        )
      })}
    </ol>
  )
}
