import type { Page } from '@playwright/test';

export function collectConsoleHealth(page: Page) {
  const errors: string[] = [];
  page.on('console', (message) => {
    if (['error', 'warning'].includes(message.type())) errors.push(`${message.type()}: ${message.text()}`);
  });
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  return {
    errors,
    assertHealthy() {
      const relevant = errors.filter((line) => !line.includes('favicon') && !line.includes('ResizeObserver'));
      if (relevant.length) throw new Error(`Console health failed:\n${relevant.join('\n')}`);
    },
  };
}
