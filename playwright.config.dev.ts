import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Docker Compose Development
 *
 * This configuration targets the local Docker Compose environment.
 * Base URL: http://localhost:8080 (paless-web service)
 *
 * For production/K3s testing, use a different config file.
 */
export default defineConfig({
  // Test directory
  testDir: './tests',

  // Look for test files in the project root as well (for temporary verification tests)
  testMatch: ['**/*.spec.ts', '**/*.test.ts'],

  // Maximum time one test can run
  timeout: 30 * 1000,

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,

  // Reporter to use
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],

  // Shared settings for all projects
  use: {
    // Base URL for all page.goto() calls
    baseURL: 'http://localhost:8080',

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'retain-on-failure',

    // Maximum time for actions like click, fill, etc.
    actionTimeout: 10 * 1000,

    // Maximum time for navigation actions
    navigationTimeout: 30 * 1000,
  },

  // Configure projects for different browsers
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Container-friendly Chromium arguments
        launchOptions: {
          args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
          ],
        },
      },
    },

    // Uncomment for multi-browser testing
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },

    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Folder for test artifacts
  outputDir: 'test-results/',

  // Screenshots folder
  snapshotPathTemplate: '{testDir}/{testFileDir}/screenshots/{arg}{ext}',

  // Global setup/teardown
  // globalSetup: undefined,
  // globalTeardown: undefined,

  // Web server configuration - NOT USED for Docker Compose testing
  // Application is already running in Docker Compose
  // Do NOT start a development server automatically
  // webServer: undefined,
});
