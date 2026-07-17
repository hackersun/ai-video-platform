import { defineConfig, devices } from '@playwright/test';

const e2ePort = process.env.PLAYWRIGHT_PORT || '3100';
const baseURL = `http://localhost:${e2ePort}`;
const chromeExecutablePath = process.env.PLAYWRIGHT_CHROME_EXECUTABLE_PATH;
const outputDir = process.env.PLAYWRIGHT_OUTPUT_DIR || '/tmp/ai-video-platform-series-studio-e2e/test-results';
const playwrightDistDir = process.env.PLAYWRIGHT_DIST_DIR || '.next-playwright';
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_EXISTING_SERVER !== '0';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  outputDir,
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    ...(chromeExecutablePath ? { launchOptions: { executablePath: chromeExecutablePath } } : {}),
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: undefined,
      },
    },
  ],
  webServer: {
    command: `NEXT_DIST_DIR=${playwrightDistDir} npx next dev -p ${e2ePort}`,
    url: `${baseURL}/workflow`,
    reuseExistingServer,
    timeout: 120 * 1000,
  },
});
