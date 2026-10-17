import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('error', (err) => {
            if (err.message && (err.message.includes('ECONNABORTED') || err.message.includes('ECONNRESET'))) {
              return;
            }
            console.error('[vite] proxy error:', err);
          });
          proxy.on('proxyReqWs', (_proxyReq, _req, socket) => {
            socket.on('error', (err: any) => {
              if (err?.message && (err.message.includes('ECONNABORTED') || err.message.includes('ECONNRESET'))) {
                return;
              }
              console.error('[vite] ws socket error:', err);
            });
          });
        },
      },
    },
  },
})

