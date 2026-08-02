import { expect, test } from '@playwright/test';

const USER_ID = 'light-theme-route-user';
const USER = { id: USER_ID, username: USER_ID, email: `${USER_ID}@example.test` };
const TOKEN = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiJsaWdodC10aGVtZS1yb3V0ZS11c2VyIn0.';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(({ token, user }) => {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem(`settings.appearance:${user.id}`, JSON.stringify({
      theme: 'light',
      accent: 'violet',
      compactNavigation: false,
      denseContent: false,
      reduceMotion: false,
    }));
  }, { token: TOKEN, user: USER });

  await page.route('**/api/v1/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/auth/me')) return route.fulfill({ json: USER });
    return route.fulfill({ json: [] });
  });
});

const CORE_LIGHT_ROUTES = [
  '/dashboard',
  '/novels',
  '/story-bibles',
  '/assets',
  '/characters',
  '/scripts',
  '/storyboards',
  '/shots',
  '/workflow',
  '/producer',
  '/quick-start',
  '/subtitles',
  '/tts',
  '/studio',
  '/studio/cards',
  '/studio/shot-review',
  '/llm-config',
  '/settings',
  '/settings/appearance',
];

for (const path of CORE_LIGHT_ROUTES) {
  test(`${path} 的浅色根画布不保留写死的深色背景`, async ({ page }) => {
    await page.goto(path);
    const root = page.locator('.min-h-screen').last();
    await expect(root).toBeVisible();
    const background = await root.evaluate((element) => {
      let current: Element | null = element;
      while (current) {
        const color = getComputedStyle(current).backgroundColor;
        if (color !== 'rgba(0, 0, 0, 0)' && color !== 'transparent') return color;
        current = current.parentElement;
      }
      return getComputedStyle(document.body).backgroundColor;
    });
    expect(background).toMatch(/^rgba?\((24[0-9]|25[0-5]), (24[0-9]|25[0-5]), (24[0-9]|25[0-5])/);

    const lowContrast = await page.evaluate(() => {
      const rgb = (value: string) => (value.match(/[\d.]+/g) || []).slice(0, 4).map(Number);
      const luminance = (value: string) => {
        const channels = rgb(value).slice(0, 3).map((item) => {
          const channel = item / 255;
          return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
      };
      const ratio = (foreground: string, backgroundColor: string) => {
        const light = Math.max(luminance(foreground), luminance(backgroundColor));
        const dark = Math.min(luminance(foreground), luminance(backgroundColor));
        return (light + 0.05) / (dark + 0.05);
      };
      const effectiveBackground = (element: Element) => {
        let current: Element | null = element;
        while (current) {
          const color = getComputedStyle(current).backgroundColor;
          const values = rgb(color);
          if (values.length === 3 || (values.length === 4 && values[3] >= 0.9)) return color;
          current = current.parentElement;
        }
        return getComputedStyle(document.body).backgroundColor;
      };

      return Array.from(document.querySelectorAll('h1, h2, h3, p, a, button, label, [role="tab"]'))
        .filter((element) => {
          const node = element as HTMLElement;
          const style = getComputedStyle(node);
          return node.innerText.trim().length > 0
            && node.offsetWidth > 0
            && node.offsetHeight > 0
            && style.visibility !== 'hidden'
            && Number(style.opacity) >= 0.6
            && !node.matches(':disabled');
        })
        .map((element) => {
          const node = element as HTMLElement;
          const style = getComputedStyle(node);
          const backgroundColor = effectiveBackground(node);
          const contrast = ratio(style.color, backgroundColor);
          const largeText = Number.parseFloat(style.fontSize) >= 18 && Number(style.fontWeight) >= 600;
          return {
            text: node.innerText.trim().replace(/\s+/g, ' ').slice(0, 60),
            contrast,
            required: largeText ? 3 : 4.5,
            color: style.color,
            backgroundColor,
          };
        })
        .filter((item) => item.contrast < item.required)
        .slice(0, 8);
    });
    expect(lowContrast).toEqual([]);
  });
}
