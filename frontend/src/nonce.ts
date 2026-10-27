import { setNonce } from 'get-nonce'

const PLACEHOLDER = '__CSP_NONCE__'

/**
 * Read the per-page CSP nonce the server writes into <meta name="csp-nonce">
 * and hand it to get-nonce, which Radix uses (through react-style-singleton)
 * to tag the few <style> elements it creates. Under the server's CSP only
 * style tags with this page's nonce are allowed (threat model T6).
 *
 * Must run before anything from Radix renders. Returns the nonce, or
 * undefined if there isn't one (Vite's dev server, or tests).
 */
export function applyCspNonce(doc: Document = document): string | undefined {
  const value = doc.querySelector('meta[name="csp-nonce"]')?.getAttribute('content') ?? ''
  if (value === '' || value === PLACEHOLDER) return undefined
  setNonce(value)
  return value
}
