// [[wikilinks]] in note text become links while the Markdown is parsed.
// Only text is looked at, so code (`inline` and fenced) is never touched,
// and text that's already inside a link is left alone. Which note a link
// opens is decided by the backend (onyx/links.py); targets are found the
// same way here: "Note#Heading|Shown" → target "Note", shown "Shown".

export const WIKILINK_PREFIX = 'onyx-note:'

const WIKILINK = /\[\[([^[\]\n]{1,300})\]\]/g

type MdNode = { type: string; value?: string; url?: string; children?: MdNode[] }

export function targetOf(raw: string): string {
  return raw.split('|', 1)[0].split('#', 1)[0].trim()
}

function shownText(raw: string): string {
  const bar = raw.indexOf('|')
  return (bar >= 0 ? raw.slice(bar + 1) : raw).trim() || raw.trim()
}

function split(value: string): MdNode[] {
  const parts: MdNode[] = []
  let last = 0
  for (const match of value.matchAll(WIKILINK)) {
    const target = targetOf(match[1])
    if (!target) continue
    if (match.index > last) parts.push({ type: 'text', value: value.slice(last, match.index) })
    parts.push({
      type: 'link',
      url: WIKILINK_PREFIX + encodeURIComponent(target),
      children: [{ type: 'text', value: shownText(match[1]) }],
    })
    last = match.index + match[0].length
  }
  if (parts.length === 0) return [{ type: 'text', value }]
  if (last < value.length) parts.push({ type: 'text', value: value.slice(last) })
  return parts
}

function walk(node: MdNode): void {
  if (!node.children || node.type === 'link' || node.type === 'linkReference') return
  node.children = node.children.flatMap((child) => {
    if (child.type === 'text' && child.value !== undefined) return split(child.value)
    walk(child)
    return [child]
  })
}

/** A remark plugin: turns [[wikilinks]] in text into links to `onyx-note:<target>`. */
export function remarkWikilinks() {
  return (tree: MdNode) => walk(tree)
}

/** The target in an `onyx-note:` address, or null for any other address. */
export function wikilinkTarget(href: string | undefined): string | null {
  if (!href?.startsWith(WIKILINK_PREFIX)) return null
  try {
    return decodeURIComponent(href.slice(WIKILINK_PREFIX.length))
  } catch {
    return null
  }
}
