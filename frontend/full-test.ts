/**
 * Full Stack E2E Test Suite
 * Tests both backend APIs and frontend pages
 */

const API_BASE = 'http://127.0.0.1:8000/api/v1';
const FRONTEND_BASE = 'http://127.0.0.1:3000';

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
  details?: any;
}

const results: TestResult[] = [];

async function fetchJSON(url: string, options: RequestInit = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  const data = await response.json().catch(() => null);
  return { status: response.status, ok: response.ok, data };
}

async function testAPI(endpoint, name, options = {}) {
  console.log(`\n🔌 API: ${name}`);
  try {
    const { status, ok, data } = await fetchJSON(`${API_BASE}${endpoint}`, options);
    if (ok) {
      results.push({ name, passed: true, details: data });
      console.log(`  ✅ ${status} - PASSED`);
      return data;
    } else {
      results.push({ name, passed: false, error: `${status}: ${JSON.stringify(data)}` });
      console.log(`  ❌ ${status} - FAILED: ${JSON.stringify(data)}`);
      return null;
    }
  } catch (error) {
    results.push({ name, passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
    return null;
  }
}

async function testPage(path, name) {
  console.log(`\n🌐 Page: ${name}`);
  try {
    const response = await fetch(`${FRONTEND_BASE}${path}`);
    const text = await response.text();
    const html = text.length > 0;

    // Check for Next.js errors in the response
    const hasError = text.includes('__NEXT_ERROR') || text.includes('NEXT_NOT_FOUND');
    const hasContent = text.includes('AI视频平台') || text.includes('DOCTYPE html');

    if (response.ok && hasContent && !hasError) {
      // Check for any API errors in the page
      const apiErrorPattern = /api\/v1\/api\/v1\//;
      if (apiErrorPattern.test(text)) {
        results.push({ name, passed: false, error: 'Duplicate /api/v1/ path detected' });
        console.log(`  ❌ FAILED: Duplicate /api/v1/ path detected`);
      } else {
        results.push({ name, passed: true, details: { htmlLength: text.length } });
        console.log(`  ✅ ${response.status} - PASSED (${text.length} bytes)`);
      }
    } else {
      results.push({ name, passed: false, error: `Status: ${response.status}` });
      console.log(`  ❌ FAILED: Status ${response.status}`);
    }
  } catch (error) {
    results.push({ name, passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
  }
}

async function testPageWithNetworkRequests(path, name) {
  console.log(`\n🌐 Page with Network: ${name}`);
  const apiCalls = [];
  const failedApis = [];

  try {
    const response = await fetch(`${FRONTEND_BASE}${path}`);
    const text = await response.text();

    if (response.ok && text.includes('AI视频平台')) {
      // Now fetch the page and check what APIs it tries to call
      // by looking at the rendered HTML for any embedded data
      results.push({ name, passed: true, details: { htmlLength: text.length } });
      console.log(`  ✅ PASSED (${text.length} bytes)`);
    } else {
      results.push({ name, passed: false, error: 'Page did not load correctly' });
      console.log(`  ❌ FAILED`);
    }
  } catch (error) {
    results.push({ name, passed: false, error: error.message });
    console.log(`  ❌ ERROR: ${error.message}`);
  }
}

async function runWorkflowTest() {
  console.log('\n\n🔄 WORKFLOW INTEGRATION TEST');

  // Test: Create a novel via API
  console.log('\n1️⃣ Creating a test novel...');
  const novel = await testAPI('/novels', 'Create Novel (POST)', {
    method: 'POST',
    body: JSON.stringify({
      title: `测试小说 ${Date.now()}`,
      description: '自动化测试创建的小说',
      genre: '科幻'
    })
  });

  if (novel) {
    // Test: Get the novel
    await testAPI(`/novels/${novel.id}`, 'Get Novel (GET)');

    // Test: Update the novel
    await testAPI(`/novels/${novel.id}`, 'Update Novel (PUT)', {
      method: 'PUT',
      body: JSON.stringify({ title: novel.title + ' (已更新)', status: 'writing' })
    });
  }

  // Test: Create a script
  console.log('\n2️⃣ Creating a test script...');
  const script = await testAPI('/scripts', 'Create Script (POST)', {
    method: 'POST',
    body: JSON.stringify({
      title: `测试剧本 ${Date.now()}`,
      description: '自动化测试创建的剧本',
      genre: '科幻',
      style: '热血'
    })
  });

  // Test: Create a character
  console.log('\n3️⃣ Creating a test character...');
  const character = await testAPI('/characters', 'Create Character (POST)', {
    method: 'POST',
    body: JSON.stringify({
      name: `测试角色 ${Date.now()}`,
      description: '自动化测试创建的角色',
      personality: '勇敢',
      appearance: '年轻'
    })
  });

  if (character) {
    await testAPI(`/characters/${character.id}`, 'Get Character (GET)');
  }

  // Test LLM Config
  console.log('\n4️⃣ Testing LLM Configuration...');
  const configs = await testAPI('/llm/configs', 'Get LLM Configs');

  if (configs && configs.length > 0) {
    const activeConfig = configs.find(c => c.is_active);
    if (activeConfig) {
      console.log(`\n  📋 Active Config: ${activeConfig.provider_id} / ${activeConfig.model_id}`);
    }
  }

  // Cleanup: Delete test data
  console.log('\n5️⃣ Cleanup test data...');
  if (novel) {
    await testAPI(`/novels/${novel.id}`, 'Delete Novel', { method: 'DELETE' });
  }
  if (script) {
    await testAPI(`/scripts/${script.id}`, 'Delete Script', { method: 'DELETE' });
  }
  if (character) {
    await testAPI(`/characters/${character.id}`, 'Delete Character', { method: 'DELETE' });
  }
}

async function main() {
  console.log('═'.repeat(60));
  console.log('🚀 AI Video Platform - Full Stack E2E Test Suite');
  console.log('═'.repeat(60));
  console.log(`\nBackend: ${API_BASE}`);
  console.log(`Frontend: ${FRONTEND_BASE}`);

  // Check if services are running
  console.log('\n📡 Checking service availability...');
  try {
    const backendCheck = await fetch(`${API_BASE}/dashboard/stats`, { signal: AbortSignal.timeout(5000) });
    console.log(`  ✅ Backend is running (${backendCheck.status})`);
  } catch (error: any) {
    console.log(`  ❌ Backend is not running! (${error.message})`);
    console.log('  Please start the backend: cd backend && uvicorn main:app --reload');
    process.exit(1);
  }

  try {
    const frontendCheck = await fetch(`${FRONTEND_BASE}`, { signal: AbortSignal.timeout(5000) });
    console.log(`  ✅ Frontend is running (${frontendCheck.status})`);
  } catch {
    console.log('  ⚠️  Frontend is not running (some tests will be skipped)');
    console.log('  Start with: npm run dev');
  }

  // Run API tests
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

  // Note: /chapters, /storyboards, /shots don't have generic list endpoints
  // They require specific IDs (e.g., /chapters/novel/{novel_id})

  // Run page tests
  console.log('\n\n' + '─'.repeat(60));
  console.log('🌐 FRONTEND PAGE TESTS');
  console.log('─'.repeat(60));

  await testPage('/dashboard', 'Dashboard');
  await testPage('/novels', 'Novels');
  await testPage('/scripts', 'Scripts');
  await testPage('/characters', 'Characters');
  await testPage('/storyboards', 'Storyboards');
  await testPage('/video-generation', 'Video Generation');
  await testPage('/tts', 'TTS');
  await testPage('/llm-config', 'LLM Config');
  await testPage('/workflow', 'Workflow');
  await testPage('/jobs', 'Jobs');
  await testPage('/analytics', 'Analytics');
  await testPage('/novels/new', 'New Novel');

  // Run workflow integration test
  console.log('\n\n' + '─'.repeat(60));
  console.log('🔄 WORKFLOW INTEGRATION TEST');
  console.log('─'.repeat(60));

  await runWorkflowTest();

  // Print summary
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
    const status = r.passed ? '✅' : '❌';
    console.log(`${status} ${r.name}`);
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

main().catch(error => {
  console.error('Test suite crashed:', error);
  process.exit(1);
});
