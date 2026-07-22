import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El proxy reenvía /v1/* a la API desplegada, así el frontend local hace
// requests "same-origin" y evita CORS (la API restringe ALLOWED_ORIGINS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/v1': {
        target: 'https://consultasbs.eurrutia.dev',
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
