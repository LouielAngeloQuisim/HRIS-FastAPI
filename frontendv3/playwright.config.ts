/**
 * Playwright E2E Test Configuration
 */

import { defineConfig, devices } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import * as path from 'node:path'

const runId = process.env.E2E_RUN_ID || `${Date.now()}-${process.pid}-${randomUUID().slice(0, 8)}`
if (!/^[a-zA-Z0-9_-]+$/.test(runId)) {
  throw new Error('E2E_RUN_ID may contain only letters, numbers, _ and -')
}
const workerCount = Number(process.env.E2E_WORKERS || 1)
if (!Number.isInteger(workerCount) || workerCount < 1 || workerCount > 4) {
  throw new Error('E2E_WORKERS must be an integer from 1 to 4')
}
const runArtifacts = path.join(process.cwd(), 'test-results', `e2e-${runId}`)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: workerCount,
  reporter: [
    ['line'],
    ['html', { outputFolder: path.join(runArtifacts, 'html') }],
    ['json', { outputFile: path.join(runArtifacts, 'results.json') }],
  ],
  outputDir: path.join(runArtifacts, 'artifacts'),
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Add more browsers as needed
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],
  webServer: process.env.E2E_EXTERNAL_SERVERS === 'true' ? undefined : [
    ...(process.env.E2E_START_BACKEND === 'true' ? [{
      command: 'uv run --directory ../backend uvicorn app.main:app --host 127.0.0.1 --port 8000',
      url: 'http://127.0.0.1:8000/api/v1/utils/health-check/',
      reuseExistingServer: false,
      timeout: 120000,
    }] : []),
    {
      command: 'pnpm dev --host 127.0.0.1',
      url: process.env.E2E_BASE_URL || 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      env: { VITE_ENABLE_DEVTOOLS: 'false' },
      timeout: 120000,
    },
  ],
})
