import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,  // Changed back to Vite default to test OAuth
    proxy: {
      '/api/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // /api/console is a page of the app, not a backend route.
        bypass: (req) => (req.url?.startsWith('/api/console') ? '/index.html' : undefined),
      },
    },
  },
  base: '/',
})
