import { defineConfig } from '@playwright/test'
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const dataDirectory = mkdtempSync(join(tmpdir(), 'ytchat-e2e-'))
const python = process.platform === 'win32' ? '.venv\\Scripts\\python.exe' : '.venv/bin/python'
export default defineConfig({
  testDir: './tests',
  workers: 1,
  timeout: 30000,
  use: { baseURL: 'http://127.0.0.1:12452', viewport: { width: 1440, height: 1000 } },
  webServer: {
    command: `${python} main.py --port 12452`,
    cwd: '..',
    env: { YTCHAT_DATA_DIR: dataDirectory },
    url: 'http://127.0.0.1:12452/api/status',
    reuseExistingServer: false,
  },
})
