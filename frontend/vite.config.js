import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue2'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }, extensions: ['.mjs', '.js', '.json', '.vue'] },
  server: { proxy: { '/api': 'http://127.0.0.1:12450', '/ws': { target: 'ws://127.0.0.1:12450', ws: true } } }
})
