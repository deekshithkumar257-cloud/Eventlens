import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// The browser only talks to the Vite server (same origin). Requests to /api/*
// are forwarded server-side to the FastAPI backend, so no backend port or
// localhost address is ever used by browser code.
const API_TARGET = process.env.EVENTLENS_API_URL || 'http://127.0.0.1:8000';

const apiProxy = {
  '/api': {
    target: API_TARGET,
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  },
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // Allow the sandbox preview host in addition to local development hosts.
    allowedHosts: ['.e2b.app', 'localhost', '127.0.0.1'],
    proxy: apiProxy,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
    allowedHosts: ['.e2b.app', 'localhost', '127.0.0.1'],
    proxy: apiProxy,
  },
});
