import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { applyCspNonce } from './nonce'
import App from './App.tsx'
import './index.css'

// Before anything renders: Radix's style tags need this page's CSP nonce.
applyCspNonce()

const root = document.getElementById('root')
if (!root) throw new Error('Missing #root element')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
