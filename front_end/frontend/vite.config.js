import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/getbestvoice': 'http://localhost:5000',
      '/generate_voice': 'http://localhost:5000',
      '/analyze_single_response': 'http://localhost:5000',
      '/analyze_whole_conversation': 'http://localhost:5000',
      '/ws': {
        target: 'ws://localhost:5000',
        ws: true,
      },
    },
  },
})
