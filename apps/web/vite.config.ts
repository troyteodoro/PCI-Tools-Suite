import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Required for HMR to work through the container port mapping.
    watch: { usePolling: true },
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://api:8000',
        changeOrigin: true,
      },
      '/healthz': { target: process.env.VITE_API_TARGET ?? 'http://api:8000' },
      '/readyz': { target: process.env.VITE_API_TARGET ?? 'http://api:8000' },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
