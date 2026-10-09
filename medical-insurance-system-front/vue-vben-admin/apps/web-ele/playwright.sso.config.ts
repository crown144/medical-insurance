import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  outputDir: '../../test-results/sso',
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5998',
    headless: true,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
  },
  webServer: {
    command:
      'pnpm --filter @vben/web-ele exec vite preview --host 127.0.0.1 --port 5998 --strictPort',
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
    url: 'http://127.0.0.1:5998',
    reuseExistingServer: !process.env.CI,
  },
});
