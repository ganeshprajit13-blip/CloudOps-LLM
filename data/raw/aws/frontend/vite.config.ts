import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        // Prevent response buffering so SSE events stream in real-time.
        // Without this, the proxy may hold the entire response until the
        // upstream closes the connection, causing all events to arrive at once.
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, _req, res) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              res.setHeader('X-Accel-Buffering', 'no')
              res.setHeader('Cache-Control', 'no-cache, no-transform')
            }
          })
        },
      },
    },
  },
  build: {
    outDir: 'dist',
  },
  // Environment variables for production deployment (Amplify/AgentCore).
  // In local dev these are empty, which triggers FastAPI mode.
  // Set via Amplify environment variables or .env.production file.
  //   VITE_AGENTCORE_ENDPOINT  — AgentCore Runtime HTTP endpoint URL
  //   VITE_COGNITO_USER_POOL_ID — Cognito User Pool ID (Phase 2)
  //   VITE_COGNITO_APP_CLIENT_ID — Cognito App Client ID (Phase 2)
  //   VITE_COGNITO_DOMAIN — Cognito Hosted UI domain (Phase 2)
})
