import { describe, expect, it } from 'vitest'
import { changeCounts, lineDiff, MAX_CELLS, withContext, type DiffLine } from './lineDiff'

/** "+x", "-x", " x" per line: easy to read in a test. */
const show = (diff: DiffLine[] | null) => diff?.map((l) => (l.kind === 'added' ? '+' : l.kind === 'removed' ? '-' : ' ') + l.text)

/** Rebuild both texts from a diff; a correct diff always gives them back. */
function rebuild(diff: DiffLine[]) {
  return {
    before: diff.filter((l) => l.kind !== 'added').map((l) => l.text).join('\n'),
    after: diff.filter((l) => l.kind !== 'removed').map((l) => l.text).join('\n'),
  }
}

describe('lineDiff', () => {
  it('no change: every line the same', () => {
    expect(show(lineDiff('a\nb\nc', 'a\nb\nc'))).toEqual([' a', ' b', ' c'])
  })

  it('a line added, removed, and changed', () => {
    expect(show(lineDiff('a\nb\nc', 'a\nb\nx\nc'))).toEqual([' a', ' b', '+x', ' c'])
    expect(show(lineDiff('a\nb\nc', 'a\nc'))).toEqual([' a', '-b', ' c'])
    expect(show(lineDiff('a\nb\nc', 'a\nB\nc'))).toEqual([' a', '-b', '+B', ' c'])
  })

  it('shows removed lines before added ones in a changed run', () => {
    expect(show(lineDiff('a\nb\nc\nd', 'a\nX\nY\nd'))).toEqual([' a', '-b', '-c', '+X', '+Y', ' d'])
  })

  it('keeps the unchanged lines between two separate edits', () => {
    expect(show(lineDiff('1\n2\n3\n4\n5', '1\nTWO\n3\n4\nFIVE'))).toEqual([' 1', '-2', '+TWO', ' 3', ' 4', '-5', '+FIVE'])
  })

  it('finds the longest run of shared lines, not just the first match', () => {
    expect(show(lineDiff('x\na\nb\nc', 'a\nb\nc\nx'))).toEqual(['-x', ' a', ' b', ' c', '+x'])
  })

  it('numbers lines as they were opened and as they are now', () => {
    expect(lineDiff('a\nb\nc', 'a\nx\nb\nc')).toEqual([
      { kind: 'same', text: 'a', oldNo: 1, newNo: 1 },
      { kind: 'added', text: 'x', newNo: 2 },
      { kind: 'same', text: 'b', oldNo: 2, newNo: 3 },
      { kind: 'same', text: 'c', oldNo: 3, newNo: 4 },
    ])
  })

  it('ignores Windows line endings in the note as opened', () => {
    expect(show(lineDiff('a\r\nb\r\n', 'a\nb\n'))).toEqual([' a', ' b', ' '])
  })

  it('a new final newline shows as an added empty line', () => {
    expect(show(lineDiff('a', 'a\n'))).toEqual([' a', '+'])
  })

  it('from empty and to empty', () => {
    expect(show(lineDiff('', 'a\nb'))).toEqual(['-', '+a', '+b'])
    expect(show(lineDiff('a\nb', ''))).toEqual(['-a', '-b', '+'])
  })

  it('treats note text as plain text', () => {
    const hostile = '<img src=x onerror=alert(1)>'
    expect(show(lineDiff('a', `a\n${hostile}`))).toEqual([' a', `+${hostile}`])
  })

  it('always gives both texts back, on many random edits', () => {
    let seed = 7
    const random = (n: number) => {
      seed = (seed * 1103515245 + 12345) % 2147483648
      return seed % n
    }
    for (let round = 0; round < 300; round++) {
      const before = Array.from({ length: random(12) }, () => 'abc'[random(3)])
      const after = before.slice()
      for (let edits = random(5); edits > 0; edits--) {
        const at = random(after.length + 1)
        if (random(2) === 0) after.splice(at, 0, 'xyz'[random(3)])
        else after.splice(at, 1)
      }
      const diff = lineDiff(before.join('\n'), after.join('\n'))!
      expect(rebuild(diff)).toEqual({ before: before.join('\n'), after: after.join('\n') })
    }
  })

  it('is the smallest change: shared lines are kept, not removed and re-added', () => {
    // a b c d e → a c e f: b and d removed, f added, nothing else.
    expect(changeCounts(lineDiff('a\nb\nc\nd\ne', 'a\nc\ne\nf')!)).toEqual({ added: 1, removed: 2 })
  })

  it('gives up (null) above the size limit, but not for a large note with one edit', () => {
    const side = Math.ceil(Math.sqrt(MAX_CELLS)) + 1
    const before = Array.from({ length: side }, (_, k) => `old ${k}`).join('\n')
    const after = Array.from({ length: side }, (_, k) => `new ${k}`).join('\n')
    expect(lineDiff(before, after)).toBeNull()

    const big = Array.from({ length: 50_000 }, (_, k) => `line ${k}`)
    const edited = big.slice()
    edited[25_000] = 'changed'
    expect(changeCounts(lineDiff(big.join('\n'), edited.join('\n'))!)).toEqual({ added: 1, removed: 1 })
  })
})

describe('withContext', () => {
  const diff = lineDiff('1\n2\n3\n4\n5\n6\n7\n8\n9\n10', '1\n2\n3\n4\n5\nSIX\n7\n8\n9\n10')!

  it('keeps 2 lines either side of a change and folds the rest', () => {
    const rows = withContext(diff)
    expect(rows.map((r) => (r.kind === 'gap' ? `…${r.count}` : r.text))).toEqual(['…3', '4', '5', '6', 'SIX', '7', '8', '…2'])
  })

  it('no changes: nothing to show', () => {
    expect(withContext(lineDiff('a\nb', 'a\nb')!)).toEqual([])
  })

  it('a change at the very start or end has no gap on that side', () => {
    const rows = withContext(lineDiff('a\nb\nc\nd\ne', 'A\nb\nc\nd\nE')!, 1)
    expect(rows.map((r) => (r.kind === 'gap' ? `…${r.count}` : r.text))).toEqual(['a', 'A', 'b', '…1', 'd', 'e', 'E'])
  })
})
