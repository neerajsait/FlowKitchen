import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'



const DEV_CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' data: blob: https://images.unsplash.com http://localhost:5000",
  "connect-src 'self' ws://localhost:5174 http://localhost:5000",
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
    port: 5174,
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
