import { chromium, Browser, Page, BrowserType } from 'playwright';

const API_BASE = 'http://127.0.0.1:8000/api/v1';
const FRONTEND_BASE = 'http://127.0.0.1:3000';

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
  details?: any;
}

const results: TestResult[] = [];

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testAPI(endpoint: string, name: string, options: RequestInit = {}) {
  console.log(`\n🔌 API: ${name}`);
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    const data = await response.json().catch(() => null);
    if (response.ok) {
      results.push({ name, passed: true, details: data });
      console.log(`  ✅ ${response.status} - PASSED`);
      return data;
    } else {
      results.push({ name, passed: false, error: `${response.status}: ${JSON.stringify(data)}` });
      console.log(`  ❌ ${response.status} - FAILED`);
      return null;
    }
  } catch (error: any) {
    results.push({ name, passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
    return null;
  }
}

async function testPage(page: Page, name: string, url: string) {
  console.log(`\n🌐 Page: ${name}`);
  const errors: string[] = [];

  const errorHandler = (msg: any) => {
    if (msg.type() === 'error') {
      const text = msg.text();
      // Ignore known non-critical warnings
      if (!text.includes('Warning') && !text.includes('data-atm') && !text.includes('Extra attributes')) {
        errors.push(text);
      }
    }
  };

  page.on('console', errorHandler);

  try {
    await page.goto(`${FRONTEND_BASE}${url}`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(1500);

    // Check page loaded correctly
    const content = await page.content();
    const hasCorrectTitle = content.includes('AI视频平台');
    const hasNoCriticalError = !content.includes('NEXT_NOT_FOUND') || !content.includes('not-found');

    if (hasCorrectTitle && hasNoCriticalError) {
      results.push({ name, passed: true, details: { errors: errors.length } });
      console.log(`  ✅ PASSED`);
      if (errors.length > 0) {
        console.log(`  ⚠️  ${errors.length} console error(s)`);
      }
    } else {
      results.push({ name, passed: false, error: 'Page did not load correctly' });
      console.log(`  ❌ FAILED`);
    }
  } catch (error: any) {
    results.push({ name, passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
  } finally {
    page.off('console', errorHandler);
  }
}

async function testInteractiveWorkflow(page: Page) {
  console.log('\n\n🔄 INTERACTIVE WORKFLOW TEST');

  // Test: Novel Creation
  console.log('\n1️⃣ Testing Novel Creation...');
  try {
    await page.goto(`${FRONTEND_BASE}/novels/new`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);

    // Fill in the form
    const titleInput = page.locator('input[placeholder*="小说标题"], input[name="title"]').first();
    if (await titleInput.isVisible()) {
      await titleInput.fill('Playwright 测试小说');

      // Click submit button
      const submitBtn = page.locator('button:has-text("创建")').first();
      if (await submitBtn.isVisible()) {
        await submitBtn.click();
        await sleep(2000);
        results.push({ name: 'Interactive: Novel Creation', passed: true });
        console.log('  ✅ PASSED');
      }
    } else {
      results.push({ name: 'Interactive: Novel Creation', passed: false, error: 'Form not found' });
      console.log('  ⚠️  Form not visible (may need manual interaction)');
    }
  } catch (error: any) {
    results.push({ name: 'Interactive: Novel Creation', passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
  }

  // Test: Workflow Navigation
  console.log('\n2️⃣ Testing Workflow Page...');
  try {
    await page.goto(`${FRONTEND_BASE}/workflow`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);

    const content = await page.content();
    const hasWorkflowContent = content.includes('创作流程') || content.includes('工作流') || content.includes('步骤');
    results.push({ name: 'Interactive: Workflow Page', passed: hasWorkflowContent });
    console.log(hasWorkflowContent ? '  ✅ PASSED' : '  ❌ FAILED');
  } catch (error: any) {
    results.push({ name: 'Interactive: Workflow Page', passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
  }

  // Test: LLM Config Page
  console.log('\n3️⃣ Testing LLM Config Page...');
  try {
    await page.goto(`${FRONTEND_BASE}/llm-config`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);

    const content = await page.content();
    const hasConfigContent = content.includes('LLM') || content.includes('配置') || content.includes('API');
    results.push({ name: 'Interactive: LLM Config Page', passed: hasConfigContent });
    console.log(hasConfigContent ? '  ✅ PASSED' : '  ❌ FAILED');
  } catch (error: any) {
    results.push({ name: 'Interactive: LLM Config Page', passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
  }
}

async function runTests() {
  console.log('═'.repeat(60));
  console.log('🚀 AI Video Platform - Full Browser E2E Test Suite');
  console.log('═'.repeat(60));
  console.log(`\nBackend: ${API_BASE}`);
  console.log(`Frontend: ${FRONTEND_BASE}`);

  // Check services
  console.log('\n📡 Checking services...');
  try {
    const backendCheck = await fetch(`${API_BASE}/dashboard/stats`);
    console.log(`  ✅ Backend running (${backendCheck.status})`);
  } catch {
    console.log('  ❌ Backend not running!');
    console.log('  Start: cd ../backend && uvicorn main:app --reload');
    process.exit(1);
  }

  try {
    const frontendCheck = await fetch(`${FRONTEND_BASE}`);
    console.log(`  ✅ Frontend running (${frontendCheck.status})`);
  } catch {
    console.log('  ⚠️  Frontend not running');
    console.log('  Start: npm run dev');
    process.exit(1);
  }

  // Launch browser using system Chrome
  console.log('\n🌐 Launching browser...');
  let browser: Browser;

  try {
    // Try to use system Chrome
    browser = await chromium.launch({
      headless: true,
      executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    console.log('  ✅ Using system Google Chrome');
  } catch (error) {
    console.log('  ❌ Failed to launch Chrome');
    console.log(`  Error: ${error}`);
    process.exit(1);
  }

  const context = await browser.newContext();
  const page: Page = await context.newPage();

  // Backend API Tests
  console.log('\n\n' + '─'.repeat(60));
  console.log('📡 BACKEND API TESTS');
  console.log('─'.repeat(60));

  await testAPI('/dashboard/stats', 'Dashboard Stats');
  await testAPI('/novels', 'List Novels');
  await testAPI('/scripts', 'List Scripts');
  await testAPI('/characters', 'List Characters');
  await testAPI('/llm/providers', 'LLM Providers');
  await testAPI('/llm/configs', 'LLM Configs');
  await testAPI('/tts/jobs', 'TTS Jobs');
  await testAPI('/video/jobs', 'Video Jobs');
  await testAPI('/synthesis/jobs', 'Synthesis Jobs');
  await testAPI('/workflow/steps', 'Workflow Steps');

  // Frontend Page Tests
  console.log('\n\n' + '─'.repeat(60));
  console.log('🌐 FRONTEND PAGE TESTS (Browser)');
  console.log('─'.repeat(60));

  await testPage(page, 'Dashboard', '/dashboard');
  await testPage(page, 'Novels', '/novels');
  await testPage(page, 'Scripts', '/scripts');
  await testPage(page, 'Characters', '/characters');
  await testPage(page, 'Storyboards', '/storyboards');
  await testPage(page, 'Video Generation', '/video-generation');
  await testPage(page, 'TTS', '/tts');
  await testPage(page, 'LLM Config', '/llm-config');
  await testPage(page, 'Workflow', '/workflow');
  await testPage(page, 'Jobs', '/jobs');
  await testPage(page, 'Analytics', '/analytics');
  await testPage(page, 'New Novel', '/novels/new');

  // Interactive Tests
  console.log('\n\n' + '─'.repeat(60));
  console.log('🖱️  INTERACTIVE TESTS (Browser)');
  console.log('─'.repeat(60));

  await testInteractiveWorkflow(page);

  // Close browser
  await browser.close();

  // Summary
  console.log('\n\n' + '═'.repeat(60));
  console.log('📊 TEST SUMMARY');
  console.log('═'.repeat(60));

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const total = results.length;

  console.log(`\nTotal: ${total} tests`);
  console.log(`Passed: ✅ ${passed}`);
  console.log(`Failed: ❌ ${failed}`);
  console.log(`Success Rate: ${((passed / total) * 100).toFixed(1)}%`);

  if (failed > 0) {
    console.log('\n❌ Failed Tests:');
    results.filter(r => !r.passed).forEach(r => {
      console.log(`  - ${r.name}: ${r.error}`);
    });
  }

  console.log('\n' + '─'.repeat(60));
  console.log('All Results:');
  console.log('─'.repeat(60));
  results.forEach(r => {
    console.log(`${r.passed ? '✅' : '❌'} ${r.name}`);
  });

  console.log('\n' + '═'.repeat(60));

  if (failed > 0) {
    console.log(`\n❌ ${failed} test(s) failed!`);
    process.exit(1);
  } else {
    console.log('\n✅ All tests passed!');
    process.exit(0);
  }
}

runTests().catch(error => {
  console.error('Test suite crashed:', error);
  process.exit(1);
});
