import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// CSP for `vite dev` ONLY. Vite's dev server injects an inline script
// (@react-refresh preamble) and inline styles for HMR, so 'unsafe-inline'
// is unavoidable here. In production the SPA is served by the Flask
// backend, which sends the strict CSP (no unsafe-inline/eval).
const DEV_CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' data: blob: https://images.unsplash.com http://localhost:5000",
  "connect-src 'self' ws://localhost:5173 http://localhost:5000",
  "font-src 'self' https://fonts.gstatic.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'"
].join('; ')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    headers: {
      'Content-Security-Policy': DEV_CSP,
      'X-Frame-Options': 'DENY',
      'X-Content-Type-Options': 'nosniff'
    }
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/testSetup.js'],
    globals: true
  }
})
