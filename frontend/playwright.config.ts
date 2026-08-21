import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const frontendDirectory = fileURLToPath(new URL('.', import.meta.url));
const backendDirectory = fileURLToPath(new URL('../backend', import.meta.url));
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173';
const backendURL = process.env.PLAYWRIGHT_BACKEND_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]]
    : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: '.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: backendDirectory,
      env: {
        MERIDIAN_ARTIFACT_DIRECTORY: '../data/generated',
        MERIDIAN_ARTIFACT_DATA_VERSION: 'test-v1',
        MERIDIAN_CORS_ORIGINS: '["http://localhost:5173"]',
        MERIDIAN_ENVIRONMENT: 'test',
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      url: `${backendURL}/api/ready`,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173',
      cwd: frontendDirectory,
      env: { VITE_API_BASE_URL: backendURL },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      url: baseURL,
    },
  ],
});
