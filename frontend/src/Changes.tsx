import { changeCounts, lineDiff, withContext } from './lineDiff'

/**
 * The edit as + / − lines against the note as it was opened (3(i) on #8).
 * Worked out from the two texts each time; no history is kept.
 */
export default function Changes({ before, after }: { before: string; after: string }) {
  const diff = lineDiff(before, after)
  if (diff === null) {
    return <p className="text-sm text-stone-500">Too many changes to compare line by line. Your text is unaffected.</p>
  }
  const { added, removed } = changeCounts(diff)
  if (added === 0 && removed === 0) return <p className="text-sm text-stone-500">No changes yet.</p>
  return (
    <div>
      <p data-testid="change-counts" className="mb-2 text-sm">
        <span className="text-emerald-700 dark:text-emerald-400">+{added}</span>{' '}
        <span className="text-rose-700 dark:text-rose-400">−{removed}</span>{' '}
        <span className="text-stone-500">since you opened it</span>
      </p>
      <ol aria-label="Changed lines" className="overflow-x-auto font-mono text-xs leading-5">
        {withContext(diff).map((row, k) => {
          if (row.kind === 'gap') {
            return (
              <li key={k} className="py-0.5 text-stone-400">
                ⋯ {row.count} unchanged {row.count === 1 ? 'line' : 'lines'}
              </li>
            )
          }
          const number = row.kind === 'removed' ? row.oldNo : row.newNo
          const text = row.text === '' ? ' ' : row.text
          return (
            <li
              key={k}
              data-kind={row.kind}
              className={`flex gap-2 whitespace-pre ${row.kind === 'added' ? 'bg-emerald-50 dark:bg-emerald-950' : row.kind === 'removed' ? 'bg-rose-50 dark:bg-rose-950' : ''}`}
            >
              <span aria-hidden="true" className="w-10 shrink-0 text-right text-stone-400 select-none">
                {number}
              </span>
              <span aria-hidden="true" className="w-3 shrink-0 select-none">
                {row.kind === 'added' ? '+' : row.kind === 'removed' ? '−' : ' '}
              </span>
              {row.kind === 'added' ? (
                <ins className="no-underline">{text}</ins>
              ) : row.kind === 'removed' ? (
                <del className="no-underline">{text}</del>
              ) : (
                <span>{text}</span>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
