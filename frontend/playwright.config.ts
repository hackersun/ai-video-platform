import { defineConfig, devices } from '@playwright/test';

const e2ePort = process.env.PLAYWRIGHT_PORT || '3100';
const baseURL = `http://localhost:${e2ePort}`;
const chromeExecutablePath = process.env.PLAYWRIGHT_CHROME_EXECUTABLE_PATH;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
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
    command: `npm run dev -- -p ${e2ePort}`,
    url: `${baseURL}/workflow`,
    reuseExistingServer: true,
    timeout: 120 * 1000,
  },
});
