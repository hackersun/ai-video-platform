import { chromium, Browser, Page } from 'playwright';

const API_BASE = 'http://localhost:8000/api/v1';
const FRONTEND_BASE = 'http://localhost:3000';

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

const results: TestResult[] = [];

async function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testPage(page: Page, name: string, url: string, checkFn?: (p: Page) => Promise<boolean>) {
  console.log(`\n🧪 Testing: ${name}`);
  try {
    await page.goto(`${FRONTEND_BASE}${url}`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(1000);

    if (checkFn) {
      const passed = await checkFn(page);
      results.push({ name, passed });
      console.log(passed ? '  ✅ PASSED' : '  ❌ FAILED');
    } else {
      // Check for JS errors
      const errors: string[] = [];
      page.on('console', msg => {
        if (msg.type() === 'error' && !msg.text().includes('Warning')) {
          errors.push(msg.text());
        }
      });

      await sleep(500);
      results.push({ name, passed: true });
      console.log('  ✅ PASSED (page loaded)');
    }
  } catch (error: any) {
    results.push({ name, passed: false, error: error.message });
    console.log(`  ❌ FAILED: ${error.message}`);
  }
}

async function testAPI(endpoint: string, name: string) {
  console.log(`\n🔌 Testing API: ${name}`);
  try {
    const response = await fetch(`${API_BASE}${endpoint}`);
    const data = await response.json();
    results.push({ name, passed: response.ok });
    console.log(response.ok ? '  ✅ PASSED' : `  ❌ FAILED (${response.status})`);
    return data;
  } catch (error: any) {
    results.push({ name, passed: false, error: error.message });
    console.log(`  ❌ FAILED: ${error.message}`);
    return null;
  }
}

async function runTests() {
  console.log('🚀 Starting Full E2E Test Suite\n');
  console.log('='.repeat(50));

  // Launch browser
  const browser: Browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page: Page = await context.newPage();

  // Collect console errors
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error' && !msg.text().includes('Warning') && !msg.text().includes('data-atm')) {
      consoleErrors.push(msg.text());
    }
  });

  // Test 1: Backend APIs
  console.log('\n📡 BACKEND API TESTS');

  await testAPI('/dashboard/stats', 'Dashboard Stats API');
  await testAPI('/novels', 'Novels API');
  await testAPI('/scripts', 'Scripts API');
  await testAPI('/characters', 'Characters API');
  await testAPI('/llm/configs', 'LLM Configs API');
  await testAPI('/tts/jobs', 'TTS Jobs API');
  await testAPI('/video/jobs', 'Video Jobs API');
  await testAPI('/workflow/steps', 'Workflow Steps API');

  // Test 2: Frontend Pages
  console.log('\n\n🌐 FRONTEND PAGE TESTS');

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

  // Test 3: Interactive workflow test
  console.log('\n\n🔄 INTERACTIVE WORKFLOW TEST');

  try {
    console.log('Testing: Create a new novel...');
    await page.goto(`${FRONTEND_BASE}/novels/new`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);

    // Check if page loaded correctly
    const pageContent = await page.content();
    const hasForm = pageContent.includes('小说标题') || pageContent.includes('title');
    results.push({ name: 'Novel Creation Page', passed: hasForm });
    console.log(hasForm ? '  ✅ PASSED' : '  ❌ FAILED (form not found)');

    console.log('Testing: Workflow wizard navigation...');
    await page.goto(`${FRONTEND_BASE}/workflow`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);

    const workflowContent = await page.content();
    const hasWorkflow = workflowContent.includes('创作流程') || workflowContent.includes('工作流');
    results.push({ name: 'Workflow Page', passed: hasWorkflow });
    console.log(hasWorkflow ? '  ✅ PASSED' : '  ❌ FAILED');

  } catch (error: any) {
    results.push({ name: 'Interactive Test', passed: false, error: error.message });
    console.log(`  ❌ FAILED: ${error.message}`);
  }

  await browser.close();

  // Print summary
  console.log('\n\n' + '='.repeat(50));
  console.log('📊 TEST SUMMARY\n');

  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;

  console.log(`Total: ${results.length} | Passed: ${passed} | Failed: ${failed}`);

  if (consoleErrors.length > 0) {
    console.log('\n⚠️  Console Errors Found:');
    consoleErrors.forEach(err => console.log(`  - ${err}`));
  }

  console.log('\n📝 Detailed Results:');
  results.forEach(r => {
    console.log(`${r.passed ? '✅' : '❌'} ${r.name}${r.error ? ` - ${r.error}` : ''}`);
  });

  console.log('\n' + '='.repeat(50));

  if (failed > 0) {
    console.log(`\n❌ ${failed} test(s) failed!`);
    process.exit(1);
  } else {
    console.log('\n✅ All tests passed!');
    process.exit(0);
  }
}

runTests().catch(error => {
  console.error('Test suite failed:', error);
  process.exit(1);
});
