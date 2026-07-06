# Studio Smart Console Manual Browser Acceptance

Date: 2026-07-06

## Scope

This pass verifies the current `main` branch from a real browser session after the Studio smart console merge, local branch cleanup, and `origin/main` push.

## Environment

- Frontend: `http://127.0.0.1:3000`
- Backend API: `http://127.0.0.1:8000/api/v1`
- Backend health: `GET /health` returned `{"status":"healthy","service":"AI视频平台","version":"1.0.0"}`
- Browser automation: Playwright Chromium
- User context: dev JWT-like token with `sub=dev-user-001`
- Data snapshot: 65 novels, 9 workflows
- Workflow sampled: `41ae6694-b5d5-4479-bd33-9fdde29137ce`

## Acceptance Results

| Area | URL | Result | Evidence |
| --- | --- | --- | --- |
| Novel production entry | `/novels` | Pass | Authenticated page showed novel management and production CTA such as `生成整书计划`. |
| Studio command console | `/studio?workflow_id=41ae6694-b5d5-4479-bd33-9fdde29137ce` | Pass | Studio shell showed readiness, blocker guidance, quick entrances, and `设定/生产/复审/操作` work areas. |
| Continuity review | `/studio/continuity-review?workflow_id=41ae6694-b5d5-4479-bd33-9fdde29137ce` | Pass | Review page showed workflow filter plus novel/entity/episode/status/sort filters. |
| Shot review deep link | `/studio/shot-review?workflow_id=41ae6694-b5d5-4479-bd33-9fdde29137ce` | Pass | Shot review page loaded without crash and showed retry/regeneration actions. |

## Browser Checks

The browser pass wrote a structured result file to:

```text
output/playwright/manual-acceptance-20260706/result.json
```

Screenshots were captured locally:

```text
output/playwright/manual-acceptance-20260706/01-novels-production-entry.png
output/playwright/manual-acceptance-20260706/02-studio-command-console.png
output/playwright/manual-acceptance-20260706/03-continuity-review.png
output/playwright/manual-acceptance-20260706/04-shot-review.png
```

Summary:

```text
passed: true
consoleErrors: 0
pageErrors: 0
```

## Known Limitation

The sampled local workflow seed does not contain `novel_id` or `chapter_id`, so this manual pass validates page reachability, command-console visibility, repair guidance, review entry points, and no-crash behavior. The full novel-context workflow remains covered by the existing automated frontend E2E and backend regression tests.

## Related Verification

Previous merge verification evidence remains:

```bash
cd backend
pytest test_novel_production_entry.py test_studio_snapshot.py test_studio_actions.py test_series_production.py tests/test_production_cards.py -q
# 42 passed

cd frontend
npm run typecheck -- --incremental false --pretty false
# passed

NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run build
# passed

NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 npm run e2e -- studio-smart-console.spec.ts
# 1 passed
```

## Real Novel Context Follow-up

- Date: 2026-07-06
- Status: Ready, not executed in this run (requires seeded acceptance fixture IDs and token)
- Default skip command:

```bash
cd frontend
npx playwright test e2e/series-studio-real-context.spec.ts --project=chromium
```

- Default skip result: `1 skipped` with skip gate message `Set REAL_CONTEXT_E2E=1 after seeding the acceptance fixture.`
- Real run command template:

```bash
cd frontend
REAL_CONTEXT_E2E=1 \
REAL_CONTEXT_E2E_TOKEN=<token> \
REAL_CONTEXT_WORKFLOW_ID=<workflow_id> \
REAL_CONTEXT_NOVEL_ID=<novel_id> \
REAL_CONTEXT_CHAPTER_ID=<chapter_id> \
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1 \
npx playwright test e2e/series-studio-real-context.spec.ts --project=chromium
```

- Coverage intended: `/studio`, `/studio/cards`, `/studio/shot-review` preserve `workflow_id`/`novel_id`/`chapter_id`.
