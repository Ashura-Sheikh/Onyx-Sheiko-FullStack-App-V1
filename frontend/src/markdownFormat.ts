// The editor toolbar's Markdown formats, as plain functions on the text and
// the selection, so each can be tested without a browser.

export type Format =
  | 'heading'
  | 'bold'
  | 'italic'
  | 'bullet'
  | 'numbered'
  | 'checkbox'
  | 'quote'
  | 'link'
  | 'wikilink'
  | 'code'

/** Replace text[start, end) with `text`, then select [selectStart, selectEnd) of the result. */
export type Edit = { start: number; end: number; text: string; selectStart: number; selectEnd: number }

const PLACEHOLDER: Partial<Record<Format, string>> = {
  bold: 'bold text',
  italic: 'italic text',
  code: 'code',
  link: 'link text',
  wikilink: 'Note name',
}

function wrap(value: string, start: number, end: number, before: string, after: string, placeholder: string): Edit {
  const selected = value.slice(start, end)
  // Already wrapped (the markers sit just outside the selection): unwrap.
  if (
    selected !== '' &&
    value.slice(start - before.length, start) === before &&
    value.slice(end, end + after.length) === after
  ) {
    return {
      start: start - before.length,
      end: end + after.length,
      text: selected,
      selectStart: start - before.length,
      selectEnd: end - before.length,
    }
  }
  const inner = selected || placeholder
  return {
    start,
    end,
    text: `${before}${inner}${after}`,
    selectStart: start + before.length,
    selectEnd: start + before.length + inner.length,
  }
}

const LINE_PREFIX: Partial<Record<Format, (index: number) => string>> = {
  heading: () => '## ',
  bullet: () => '- ',
  checkbox: () => '- [ ] ',
  quote: () => '> ',
  numbered: (index) => `${index + 1}. `,
}

// What each line format looks like on a line that already has it.
const HAS_PREFIX: Partial<Record<Format, RegExp>> = {
  heading: /^#{1,6} /,
  bullet: /^[-*+] (?!\[[ xX]\] )/,
  checkbox: /^[-*+] \[[ xX]\] /,
  quote: /^> ?/,
  numbered: /^\d+[.)] /,
}

// Removed before a different line format is added (a bullet becomes a checkbox, not "- - [ ] ").
const ANY_LIST_OR_HEADING = /^(#{1,6} |[-*+] \[[ xX]\] |[-*+] |\d+[.)] |> ?)/

function lines(value: string, start: number, end: number, format: Format): Edit {
  const from = value.lastIndexOf('\n', start - 1) + 1
  // A selection ending just after a newline doesn't take in the next line.
  const last = end > start && value[end - 1] === '\n' ? end - 1 : end
  const nextNewline = value.indexOf('\n', last)
  const to = nextNewline === -1 ? value.length : nextNewline
  const block = value.slice(from, to).split('\n')
  const has = HAS_PREFIX[format]!
  const prefix = LINE_PREFIX[format]!
  const allHave = block.some((line) => line !== '') && block.every((line) => line === '' || has.test(line))
  let counter = 0
  const changed = block.map((line) => {
    if (allHave) return line.replace(has, '')
    if (line === '' && block.length > 1) return line
    return prefix(counter++) + line.replace(ANY_LIST_OR_HEADING, '')
  })
  const text = changed.join('\n')
  // A single empty line: put the cursor after the new prefix, ready to type.
  const selectAll = !(block.length === 1 && block[0] === '')
  return { start: from, end: to, text, selectStart: selectAll ? from : from + text.length, selectEnd: from + text.length }
}

export function applyFormat(value: string, start: number, end: number, format: Format): Edit {
  switch (format) {
    case 'bold':
      return wrap(value, start, end, '**', '**', PLACEHOLDER.bold!)
    case 'italic':
      return wrap(value, start, end, '*', '*', PLACEHOLDER.italic!)
    case 'wikilink':
      return wrap(value, start, end, '[[', ']]', PLACEHOLDER.wikilink!)
    case 'code': {
      const selected = value.slice(start, end)
      if (!selected.includes('\n')) return wrap(value, start, end, '`', '`', PLACEHOLDER.code!)
      // Several lines: a fenced code block, each fence on its own line.
      const before = start === 0 || value[start - 1] === '\n' ? '```\n' : '\n```\n'
      const after = selected.endsWith('\n') ? '```\n' : '\n```'
      return {
        start,
        end,
        text: `${before}${selected}${after}`,
        selectStart: start + before.length,
        selectEnd: start + before.length + selected.length,
      }
    }
    case 'link': {
      const label = value.slice(start, end) || PLACEHOLDER.link!
      const text = `[${label}](https://)`
      // Select the address, the part still to fill in.
      const addressStart = start + label.length + 3
      return { start, end, text, selectStart: addressStart, selectEnd: addressStart + 'https://'.length }
    }
    default:
      return lines(value, start, end, format)
  }
}

/** The text after an edit (used where the browser can't apply it, as in tests). */
export function applied(value: string, edit: Edit): string {
  return value.slice(0, edit.start) + edit.text + value.slice(edit.end)
}

export const TOOLBAR: { format: Format; label: string; symbol: string; shortcut?: string }[] = [
  { format: 'heading', label: 'Heading', symbol: 'H' },
  { format: 'bold', label: 'Bold', symbol: 'B', shortcut: 'b' },
  { format: 'italic', label: 'Italic', symbol: 'I', shortcut: 'i' },
  { format: 'bullet', label: 'Bulleted list', symbol: '•' },
  { format: 'numbered', label: 'Numbered list', symbol: '1.' },
  { format: 'checkbox', label: 'Checkbox', symbol: '☐' },
  { format: 'quote', label: 'Quote', symbol: '❝' },
  { format: 'link', label: 'Link', symbol: '🔗' },
  { format: 'wikilink', label: 'Wikilink', symbol: '[[ ]]' },
  { format: 'code', label: 'Code', symbol: '</>' },
]
