import { defineConfig } from '@playwright/test';

/**
 * Playwright configuration for browser verification testing.
 *
 * This config is used by agents for one-off UI verification after deploying to K3s.
 * Test files are temporary and should NOT be committed.
 *
 * Usage:
 *   npx playwright test verify.spec.ts --project=chromium
 *   npx playwright screenshot http://host.docker.internal:30080 screenshots/homepage.png
 */
export default defineConfig({
  testDir: '.',
  timeout: 30000,
  expect: {
    timeout: 5000,
  },
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  reporter: 'list',

  use: {
    // K3s services are accessible via host.docker.internal from containers
    baseURL: 'http://host.docker.internal:30080',

    // Capture trace and screenshot on failure for debugging
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',

    // Headless mode for container environments
    headless: true,
  },

  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        // Chrome-specific args for container environments
        launchOptions: {
          args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
          ],
        },
      },
    },
  ],

  // Screenshots directory
  outputDir: 'screenshots/',
});
