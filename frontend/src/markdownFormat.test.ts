import { describe, expect, it } from 'vitest'
import { applied, applyFormat, TOOLBAR, type Format } from './markdownFormat'

/** "|" marks the selection: one "|" is the cursor, two surround the selection. */
function run(marked: string, format: Format): string {
  const start = marked.indexOf('|')
  const second = marked.indexOf('|', start + 1)
  const end = second === -1 ? start : second - 1
  const value = marked.replace(/\|/g, '')
  const edit = applyFormat(value, start, end, format)
  const out = applied(value, edit)
  return edit.selectStart === edit.selectEnd
    ? `${out.slice(0, edit.selectStart)}|${out.slice(edit.selectStart)}`
    : `${out.slice(0, edit.selectStart)}|${out.slice(edit.selectStart, edit.selectEnd)}|${out.slice(edit.selectEnd)}`
}

describe('wrapping formats', () => {
  it.each<[Format, string, string]>([
    ['bold', 'a |word| b', 'a **|word|** b'],
    ['bold', 'a | b', 'a **|bold text|** b'],
    ['bold', 'a **|word|** b', 'a |word| b'], // pressed again: unwrapped
    ['italic', '|word|', '*|word|*'],
    ['italic', '|', '*|italic text|*'],
    ['wikilink', 'see |Atlas|', 'see [[|Atlas|]]'],
    ['wikilink', 'see |', 'see [[|Note name|]]'],
    ['code', 'run |npm ci| now', 'run `|npm ci|` now'],
    ['link', '|Onyx|', '[Onyx](|https://|)'],
    ['link', '|', '[link text](|https://|)'],
  ])('%s: %j → %j', (format, before, after) => {
    expect(run(before, format)).toBe(after)
  })

  it('code over several lines makes a fenced block', () => {
    expect(run('intro\n|a\nb|\nend', 'code')).toBe('intro\n```\n|a\nb|\n```\nend')
    expect(run('intro |a\nb|', 'code')).toBe('intro \n```\n|a\nb|\n```')
  })
})

describe('line formats', () => {
  it.each<[Format, string, string]>([
    ['heading', 'Title|', '|## Title|'],
    ['heading', '## Ti|tle', '|Title|'], // pressed again: removed
    ['heading', '# Ti|tle', '|Title|'],
    ['bullet', '|one\ntwo|', '|- one\n- two|'],
    ['bullet', '|- one\n- two|', '|one\ntwo|'],
    ['bullet', '|- [ ] task|', '|- task|'], // a checkbox becomes a bullet, not "- - [ ] "
    ['numbered', '|a\nb\nc|', '|1. a\n2. b\n3. c|'],
    ['numbered', '|1. a\n2. b|', '|a\nb|'],
    ['checkbox', 'buy |milk', '|- [ ] buy milk|'],
    ['checkbox', '|- one|', '|- [ ] one|'],
    ['checkbox', '- [x] do|ne', '|done|'],
    ['quote', '|said|', '|> said|'],
    ['quote', '> sa|id', '|said|'],
  ])('%s: %j → %j', (format, before, after) => {
    expect(run(before, format)).toBe(after)
  })

  it('only changes the lines the selection touches', () => {
    expect(run('keep\n|a\nb|\nkeep', 'bullet')).toBe('keep\n|- a\n- b|\nkeep')
  })

  it('a selection ending at the start of a line leaves that line alone', () => {
    expect(run('|a\n|b', 'bullet')).toBe('|- a|\nb')
  })

  it('blank lines inside a selection stay blank', () => {
    expect(run('|a\n\nb|', 'numbered')).toBe('|1. a\n\n2. b|')
  })

  it('on an empty line the cursor goes after the new marker, ready to type', () => {
    expect(run('text\n|', 'checkbox')).toBe('text\n- [ ] |')
    expect(run('|', 'heading')).toBe('## |')
  })
})

describe('toolbar', () => {
  it('has the formats Sheikh chose, each once', () => {
    expect(TOOLBAR.map((t) => t.label)).toEqual([
      'Heading',
      'Bold',
      'Italic',
      'Bulleted list',
      'Numbered list',
      'Checkbox',
      'Quote',
      'Link',
      'Wikilink',
      'Code',
    ])
  })
})
