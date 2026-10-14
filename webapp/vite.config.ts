import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The production build is served by FastAPI at /ui, so assets use relative paths.
// In development, /api is proxied to the FastAPI backend on port 8000.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    rollupOptions: { output: { manualChunks: { charts: ['recharts'], vendor: ['react', 'react-dom', 'react-router-dom'] } } },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
