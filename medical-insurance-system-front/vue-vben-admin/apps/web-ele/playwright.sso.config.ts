import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';

const baseURL = `${(process.env.PLAYWRIGHT_SSO_BASE_URL || 'http://127.0.0.1:5998').replace(/\/+$/, '')}/`;
const basePath = new URL(baseURL).pathname;
const quotedBasePath = `'${basePath.replaceAll("'", "'\\''")}'`;

export default defineConfig({
  testDir: './e2e',
  outputDir: '../../test-results/sso',
  workers: 1,
  use: {
    baseURL,
    headless: true,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
  },
  webServer: {
    command: `pnpm --filter @vben/web-ele exec vite preview --host 127.0.0.1 --port 5998 --strictPort --base ${quotedBasePath}`,
    cwd: fileURLToPath(new URL('../../', import.meta.url)),
    url: baseURL,
    reuseExistingServer: !process.env.CI,
  },
});
