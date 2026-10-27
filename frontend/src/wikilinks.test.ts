import { describe, expect, it } from 'vitest'
import { remarkWikilinks, targetOf, WIKILINK_PREFIX, wikilinkTarget } from './wikilinks'

type Node = { type: string; value?: string; url?: string; children?: Node[] }

function run(tree: Node): Node {
  remarkWikilinks()(tree)
  return tree
}

const text = (value: string): Node => ({ type: 'text', value })

describe('wikilinks', () => {
  it('turns [[links]] in text into links, keeping the text around them', () => {
    const tree = run({ type: 'paragraph', children: [text('See [[Atlas]] and [[Harbor#Plan|the plan]].')] })
    expect(tree.children).toEqual([
      text('See '),
      { type: 'link', url: `${WIKILINK_PREFIX}Atlas`, children: [text('Atlas')] },
      text(' and '),
      { type: 'link', url: `${WIKILINK_PREFIX}Harbor`, children: [text('the plan')] },
      text('.'),
    ])
  })

  it('leaves code and existing links alone', () => {
    const code: Node = { type: 'inlineCode', value: '[[Atlas]]' }
    const link: Node = { type: 'link', url: 'https://example.com', children: [text('[[Atlas]]')] }
    const tree = run({ type: 'paragraph', children: [code, link] })
    expect(tree.children).toEqual([code, link])
  })

  it('looks inside nested nodes like emphasis and list items', () => {
    const tree = run({ type: 'list', children: [{ type: 'listItem', children: [{ type: 'emphasis', children: [text('[[Deep]]')] }] }] })
    expect(tree.children?.[0].children?.[0].children?.[0]).toMatchObject({ type: 'link', url: `${WIKILINK_PREFIX}Deep` })
  })

  it('ignores empty targets', () => {
    expect(run({ type: 'paragraph', children: [text('[[#only heading]] [[ ]]')] }).children).toEqual([text('[[#only heading]] [[ ]]')])
  })

  it('targets match the backend: heading and shown text dropped, trimmed', () => {
    expect(targetOf(' Note #Heading|Shown ')).toBe('Note')
  })

  it('reads the target back only from our own addresses', () => {
    expect(wikilinkTarget(`${WIKILINK_PREFIX}${encodeURIComponent('Folder/A note')}`)).toBe('Folder/A note')
    expect(wikilinkTarget('https://example.com')).toBeNull()
    expect(wikilinkTarget(`${WIKILINK_PREFIX}%E0%A4%A`)).toBeNull()
    expect(wikilinkTarget(undefined)).toBeNull()
  })
})
