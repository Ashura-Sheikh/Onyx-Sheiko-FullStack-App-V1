// What the Read view shows of a note's body, so the editor's preview matches
// it. The same rules as backend/onyx/frontmatter.py (without_sections and
// without_first_heading) with summary.HIDDEN_SECTIONS; readView.test.ts
// checks them on the same cases.

export const HIDDEN_SECTIONS = ['Status History', 'Context']

const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/

function heading(line: string): { level: number; title: string } | null {
  const match = HEADING.exec(line.replace(/\r$/, ''))
  return match ? { level: match[1].length, title: match[2] } : null
}

/** The body without each heading in `titles` and everything under it, up to the next heading of the same or a higher level. */
export function withoutSections(body: string, titles: string[]): string {
  const kept: string[] = []
  let skipLevel: number | null = null
  for (const line of body.split('\n')) {
    const h = heading(line)
    if (h) {
      if (skipLevel !== null && h.level <= skipLevel) skipLevel = null
      if (skipLevel === null && titles.includes(h.title)) {
        skipLevel = h.level
        continue
      }
    }
    if (skipLevel === null) kept.push(line)
  }
  return kept.join('\n')
}

/** Drop the first level-1 heading if it's just the title, which the page shows on its own. */
export function withoutFirstHeading(body: string, title: string): string {
  const lines = body.split('\n')
  for (let index = 0; index < lines.length; index++) {
    if (lines[index].trim() === '') continue
    const h = heading(lines[index])
    if (h && h.level === 1 && h.title === title) return lines.slice(index + 1).join('\n')
    return body
  }
  return body
}

/** The body as the Read view shows it. */
export function shownBody(body: string, title: string): string {
  return withoutFirstHeading(withoutSections(body, HIDDEN_SECTIONS), title).replace(/^\n+|\n+$/g, '')
}
