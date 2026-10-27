import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { applyCspNonce } from './nonce'
import { applyTheme, initialTheme } from './theme'
import App from './App.tsx'
import './index.css'

// Before anything renders: Radix's style tags need this page's CSP nonce,
// and the page should start in the right theme.
applyCspNonce()
applyTheme(initialTheme())

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
