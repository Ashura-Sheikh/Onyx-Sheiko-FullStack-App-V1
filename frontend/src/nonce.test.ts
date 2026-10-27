import { getNonce, setNonce } from 'get-nonce'
import { afterEach, describe, expect, it } from 'vitest'
import { applyCspNonce } from './nonce'

function docWithMeta(content: string | null): Document {
  const doc = document.implementation.createHTMLDocument('t')
  if (content !== null) {
    const meta = doc.createElement('meta')
    meta.setAttribute('name', 'csp-nonce')
    meta.setAttribute('content', content)
    doc.head.append(meta)
  }
  return doc
}

afterEach(() => setNonce(''))

describe('applyCspNonce', () => {
  it('hands the server nonce to get-nonce (used by Radix style tags)', () => {
    expect(applyCspNonce(docWithMeta('n0nce-value'))).toBe('n0nce-value')
    expect(getNonce()).toBe('n0nce-value')
  })

  it('ignores the unreplaced placeholder (dev server)', () => {
    expect(applyCspNonce(docWithMeta('__CSP_NONCE__'))).toBeUndefined()
    expect(getNonce()).toBeFalsy()
  })

  it('copes with no meta tag', () => {
    expect(applyCspNonce(docWithMeta(null))).toBeUndefined()
  })
})
