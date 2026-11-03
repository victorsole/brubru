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
        // /api/try is a page of the app, not a backend route; /api/console/ forwards to it.
        bypass: (req) => (/^\/api\/(try|console)(\/|\?|$)/.test(req.url ?? '') ? '/index.html' : undefined),
      },
    },
  },
  base: '/',
})
