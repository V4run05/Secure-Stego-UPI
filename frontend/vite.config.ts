import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  assetsInclude: ['**/*.svg', '**/*.csv'],

  server: {
    host: '0.0.0.0',
    port: 5000,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
        // Return a proper JSON error instead of an empty response when the
        // backend is not running — this prevents "Unexpected end of JSON input"
        // in the browser.
        configure: (proxy) => {
          proxy.on('error', (err, _req, res) => {
            const msg = JSON.stringify({
              error: 'Backend unavailable',
              detail: err.message,
            });
            if ('writeHead' in res && typeof res.writeHead === 'function') {
              res.writeHead(503, {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(msg),
              });
              res.end(msg);
            }
          });
        },
      },
    },
  },
})
