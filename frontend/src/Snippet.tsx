import type { SearchResult } from './api'

/** A search snippet: plain text, with the matched words highlighted. */
export default function Snippet({ parts }: { parts: SearchResult['snippet'] }) {
  if (parts.length === 0) return null
  return (
    <span className="text-xs text-stone-500">
      {parts.map((part, index) =>
        part.match ? (
          <mark key={index} className="rounded bg-amber-200 px-0.5 text-stone-900 dark:bg-amber-800 dark:text-stone-100">
            {part.text}
          </mark>
        ) : (
          <span key={index}>{part.text}</span>
        ),
      )}
    </span>
  )
}
