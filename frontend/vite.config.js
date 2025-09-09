import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    target: 'esnext',
    minify: 'terser',
    rollupOptions: {
      output: {
        manualChunks: undefined
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(process.cwd(), 'src')
    }
  },
  define: {
    'process.env': process.env
  }
})