// Line-by-line changes between the note as it was opened and the text being
// edited (3(i) on #8). Nothing is stored: it's worked out from the two texts
// each time, so there's no history.
//
// Lines the two texts share at the start and end are matched first (most
// edits are in one place); the rest is matched by longest common
// subsequence. That table is (lines left) × (lines left) cells, so above
// MAX_CELLS the diff isn't worked out and null is returned instead of
// freezing the page.

export type DiffLine =
  | { kind: 'same'; text: string; oldNo: number; newNo: number }
  | { kind: 'removed'; text: string; oldNo: number }
  | { kind: 'added'; text: string; newNo: number }

export type DiffRow = DiffLine | { kind: 'gap'; count: number }

export const MAX_CELLS = 4_000_000

/** A browser text box gives "\n"; a note on disk may use "\r\n". */
const lines = (text: string) => text.replace(/\r\n/g, '\n').split('\n')

/** Every line of `before` and `after`, in order, marked same, removed or added; null if too large to compare. */
export function lineDiff(before: string, after: string): DiffLine[] | null {
  const a = lines(before)
  const b = lines(after)
  let start = 0
  while (start < a.length && start < b.length && a[start] === b[start]) start++
  let endA = a.length
  let endB = b.length
  while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) {
    endA--
    endB--
  }
  const n = endA - start
  const m = endB - start
  if (n * m > MAX_CELLS) return null

  // lcs[i * (m + 1) + j]: longest common run of a[start+i..endA) and b[start+j..endB).
  // Uint16 is enough: with n × m ≤ MAX_CELLS, the shorter side is ≤ 2,000 lines.
  const width = m + 1
  const lcs = new Uint16Array((n + 1) * width)
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i * width + j] =
        a[start + i] === b[start + j] ? lcs[(i + 1) * width + j + 1] + 1 : Math.max(lcs[(i + 1) * width + j], lcs[i * width + j + 1])
    }
  }

  const out: DiffLine[] = []
  for (let k = 0; k < start; k++) out.push({ kind: 'same', text: a[k], oldNo: k + 1, newNo: k + 1 })
  let i = 0
  let j = 0
  while (i < n || j < m) {
    if (i < n && j < m && a[start + i] === b[start + j]) {
      out.push({ kind: 'same', text: a[start + i], oldNo: start + i + 1, newNo: start + j + 1 })
      i++
      j++
    } else if (j < m && (i === n || lcs[i * width + j + 1] >= lcs[(i + 1) * width + j])) {
      out.push({ kind: 'added', text: b[start + j], newNo: start + j + 1 })
      j++
    } else {
      out.push({ kind: 'removed', text: a[start + i], oldNo: start + i + 1 })
      i++
    }
  }
  // Removed lines before added ones in each changed run, the usual reading order.
  for (let s = 0; s < out.length; ) {
    if (out[s].kind === 'same') {
      s++
      continue
    }
    let e = s
    while (e < out.length && out[e].kind !== 'same') e++
    const run = out.slice(s, e)
    out.splice(s, e - s, ...run.filter((l) => l.kind === 'removed'), ...run.filter((l) => l.kind === 'added'))
    s = e
  }
  for (let k = 0; k < a.length - endA; k++) {
    out.push({ kind: 'same', text: a[endA + k], oldNo: endA + k + 1, newNo: endB + k + 1 })
  }
  return out
}

/** How many lines were added and removed. */
export function changeCounts(diff: DiffLine[]): { added: number; removed: number } {
  let added = 0
  let removed = 0
  for (const line of diff) {
    if (line.kind === 'added') added++
    else if (line.kind === 'removed') removed++
  }
  return { added, removed }
}

/** Only the changed lines, with `context` unchanged lines around each; the rest becomes gaps. */
export function withContext(diff: DiffLine[], context = 2): DiffRow[] {
  const keep = diff.map(() => false)
  diff.forEach((line, k) => {
    if (line.kind === 'same') return
    for (let c = Math.max(0, k - context); c <= Math.min(diff.length - 1, k + context); c++) keep[c] = true
  })
  const rows: DiffRow[] = []
  let skipped = 0
  diff.forEach((line, k) => {
    if (keep[k]) {
      if (skipped > 0) rows.push({ kind: 'gap', count: skipped })
      skipped = 0
      rows.push(line)
    } else skipped++
  })
  if (skipped > 0 && rows.length > 0) rows.push({ kind: 'gap', count: skipped })
  return rows
}
