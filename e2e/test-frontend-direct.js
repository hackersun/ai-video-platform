/**
 * Direct frontend validation script
 * Tests all pages with real data, captures errors, and reports actionable results
 */
const { chromium } = require('@playwright/test');

const BASE_URL = 'http://localhost:3000';
const API_BASE = 'http://localhost:8000/api/v1';

// Pages to test in order
const PAGES = [
  { name: 'Dashboard', path: '/dashboard' },
  { name: 'Novels List', path: '/novels' },
  { name: 'Novels New', path: '/novels/new' },
  { name: 'Characters', path: '/characters' },
  { name: 'Scripts', path: '/scripts' },
  { name: 'Storyboards', path: '/storyboards' },
  { name: 'Shots', path: '/shots' },
  { name: 'Video Generation', path: '/video-generation' },
  { name: 'TTS', path: '/tts' },
  { name: 'Synthesis', path: '/synthesis' },
  { name: 'LLM Config', path: '/llm-config' },
  { name: 'Jobs', path: '/jobs' },
  { name: 'Workflow', path: '/workflow' },
  { name: 'Teams', path: '/teams' },
  { name: 'Templates', path: '/templates' },
  { name: 'Analytics', path: '/analytics' },
  { name: 'Settings', path: '/settings' },
];

async function login(page) {
  console.log('  Logging in...');

  // Set auth token directly to bypass login UI
  const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwZmVhNTQ4Ny1lNmViLTQ2NzQtYThiZS1hMDRiY2Q5MGUyYmEiLCJleHAiOjE3NzQ1OTA3ODksInR5cGUiOiJhY2Nlc3MifQ.G1nPgH_KvKOYZ6EtgZz3CebjLTRH4w8mLQYFs_A9kc4';
  const user = { id: '0fea5487-e6eb-4674-a8be-a04bcd90e2ba', username: 'autotest', email: 'autotest@test.com' };

  // Inject token before navigating
  await page.goto(`${BASE_URL}/login`);
  await page.evaluate(([t, u]) => {
    localStorage.setItem('auth_token', t);
    localStorage.setItem('user', JSON.stringify(u));
  }, [token, user]);
  await page.goto(`${BASE_URL}/dashboard`);
  await page.waitForLoadState('networkidle');
  console.log('  Auth token set, redirected to dashboard');
  return true;
}

async function testPage(page, pageInfo) {
  const results = {
    page: pageInfo.name,
    path: pageInfo.path,
    status: 'OK',
    errors: [],
    warnings: [],
    apiCalls: [],
    screenshot: null,
  };

  const consoleMessages = [];
  const apiCalls = [];

  // Capture console messages
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleMessages.push({ type: 'error', text: msg.text() });
    }
  });

  // Capture ALL network responses with their full URLs
  page.on('response', resp => {
    const url = resp.url();
    if (url.includes('localhost:8000') || url.includes('/api/')) {
      const status = resp.status();
      const shortUrl = url.replace('http://localhost:8000/api/v1', '/api/v1').replace('http://localhost:8000', '').replace('https://localhost:8000', '');
      apiCalls.push({ url: shortUrl, status });
      if (status >= 400) {
        results.warnings.push(`HTTP ${status}: ${shortUrl}`);
      }
    }
  });

  // Also capture request failures
  page.on('requestfailed', req => {
    const url = req.url();
    if (url.includes('localhost:8000')) {
      results.warnings.push(`FAILED: ${url.replace('http://localhost:8000', '')}`);
    }
  });

  try {
    await page.goto(`${BASE_URL}${pageInfo.path}`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000); // Wait for any async operations

    // Check page title
    const title = await page.title();
    results.title = title;

    // Check for actual error states (red alert cards, loading failed messages)
    const loadingFailed = await page.locator('text=/加载失败|出错了|网络错误|加载中.*失败/i').count();
    const redAlertCards = await page.locator('.bg-red-500, [class*="bg-red-500"], [class*="bg-red-500/"], .bg-red\\-500, [class*="bg-red/"]').count();
    const errorCard = await page.locator('[class*="bg-red"]').count();
    if (loadingFailed > 0) {
      results.status = 'ERROR';
      results.errors.push('Page shows loading failed message');
    }

    // Check for blank/empty states that shouldn't be blank
    const bodyText = await page.locator('body').innerText();
    if (bodyText.length < 50) {
      results.warnings.push('Page content appears very short');
    }

    // Report console errors (filter out React warnings)
    for (const msg of consoleMessages) {
      // Filter out known non-critical errors
      if (msg.text.includes('Failed to load resource') && msg.text.includes('favicon')) continue;
      if (msg.text.includes('websocket')) continue;
      if (msg.text.includes('Warning:')) continue; // React warnings
      if (msg.text.includes('net::ERR_CONNECTION_REFUSED')) {
        results.warnings.push(`Network: Connection refused - backend may be down`);
      } else if (msg.text.includes('net::ERR')) {
        results.warnings.push(`Network: ${msg.text.substring(0, 100)}`);
      } else {
        results.errors.push(`Console error: ${msg.text.substring(0, 150)}`);
      }
    }

    // Report API issues
    for (const api of apiCalls) {
      if (api.status >= 500) {
        results.errors.push(`Server error: ${api.url} (${api.status})`);
        results.status = 'BROKEN';
      } else if (api.status >= 400) {
        results.warnings.push(`API error: ${api.url} (${api.status})`);
        if (results.status === 'OK') results.status = 'WARN';
      }
    }

    if (results.errors.length > 0 && results.status !== 'BROKEN') {
      results.status = 'ERROR';
    }

  } catch (e) {
    results.status = 'CRASH';
    results.errors.push(`Page crash: ${e.message}`);
  }

  results.apiCalls = apiCalls;
  return results;
}

async function main() {
  console.log('=== AI Video Platform - Frontend Validation ===\n');

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  // Login first
  const loggedIn = await login(page);
  if (!loggedIn) {
    console.log('FATAL: Could not login. Cannot proceed with tests.');
    await browser.close();
    process.exit(1);
  }

  const allResults = [];
  const brokenPages = [];
  const errorPages = [];
  const warnPages = [];

  for (const pageInfo of PAGES) {
    console.log(`\nTesting: ${pageInfo.name} (${pageInfo.path})...`);
    const result = await testPage(page, pageInfo);
    allResults.push(result);

    const icon = result.status === 'OK' ? '✅' : result.status === 'WARN' ? '⚠️' : result.status === 'ERROR' ? '❌' : '💥';
    console.log(`  Status: ${icon} ${result.status}`);

    if (result.errors.length > 0) {
      for (const err of result.errors) {
        console.log(`    ERROR: ${err}`);
      }
    }
    if (result.warnings.length > 0) {
      for (const warn of result.warnings) {
        console.log(`    WARN: ${warn}`);
      }
    }

    if (result.status === 'BROKEN' || result.status === 'CRASH') brokenPages.push(result);
    else if (result.status === 'ERROR') errorPages.push(result);
    else if (result.status === 'WARN') warnPages.push(result);
  }

  // Summary
  console.log('\n\n=== SUMMARY ===');
  console.log(`Total pages tested: ${PAGES.length}`);
  console.log(`✅ OK: ${PAGES.length - brokenPages.length - errorPages.length - warnPages.length}`);
  console.log(`⚠️  WARN: ${warnPages.length}`);
  console.log(`❌ ERROR: ${errorPages.length}`);
  console.log(`💥 BROKEN: ${brokenPages.length}`);

  if (brokenPages.length > 0) {
    console.log('\n=== BROKEN PAGES (Must Fix) ===');
    for (const p of brokenPages) {
      console.log(`\n  ${p.page} (${p.path}):`);
      for (const e of p.errors) console.log(`    - ${e}`);
    }
  }

  if (errorPages.length > 0) {
    console.log('\n=== ERROR PAGES ===');
    for (const p of errorPages) {
      console.log(`\n  ${p.page} (${p.path}):`);
      for (const e of p.errors) console.log(`    - ${e}`);
    }
  }

  if (warnPages.length > 0) {
    console.log('\n=== WARN PAGES ===');
    for (const p of warnPages) {
      console.log(`\n  ${p.page} (${p.path}):`);
      for (const w of p.warnings) console.log(`    - ${w}`);
    }
  }

  await browser.close();
  console.log('\n\nDone. Fix broken/error pages first, then re-run this script.\n');
}

main().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
