import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// Разрешаем открывать dev/preview-сервер по ссылке GitHub Codespaces (*.app.github.dev)
const allowedHosts = ['.app.github.dev']

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { allowedHosts },
  preview: { allowedHosts },
  build: { chunkSizeWarningLimit: 1500 },
})
