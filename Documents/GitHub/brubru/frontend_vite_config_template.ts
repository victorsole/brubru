// frontend/vite.config.ts
// Vite configuration for Brubru frontend (port 3000)

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 3000,
    host: true, // Listen on all addresses
    proxy: {
      // Proxy API requests to backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@shared': path.resolve(__dirname, '../shared'),
    }
  },

  build: {
    outDir: 'dist',
    sourcemap: true,
    // Optimize for production
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['@headlessui/react'], // Add UI library if used
        }
      }
    }
  },

  css: {
    preprocessorOptions: {
      // If using SCSS/SASS
      // scss: {
      //   additionalData: `@import "@/styles/variables.scss";`
      // }
    }
  }
})
