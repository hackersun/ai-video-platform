# Maintenance verification — 2026-11-06 (Asia/Shanghai)

## Changes and local commits
- 2cd27e50: four-chapter helper follows saved novel detail redirect.
- e651851c: remove duplicate billing ambient-env fixture; shared conftest remains owner.
- 333379ae: reset legacy LLMConfig and user-scope model-center defaults, preserving other users/project scopes; regression included.
- 20282176 + 29235911: runtime tiny-PNG fixture for mocked UI specs, actual image-decode assertion, and /tmp-aware SQLite test (no runtime guard changed); frontend target compatibility corrected.
- 3d1fdf07 + bf3042c5: bounded chunked assets/voice/novel uploads; S3 async stream and Qiniu file-handle multipart; obsolete parser imports removed. Limits and remaining gateway responsibility are documented in streaming-uploads.md.
- 8207f242: full browser regression exposed the same obsolete redirect in comprehensive chapter creation; update current chapter dialog and remove silent conditional skipping. Redirect patterns explicitly exclude /novels/new.

## Fresh verification evidence
- Workspace backend full suite: 2427 passed, 3 skipped, 0 failed.
- Clean clone /tmp/avp-clean-final-20261106: 2427 passed, 3 skipped, 0 failed.
- Fresh clean clone /tmp/avp-clean-head-20261106 (bf3042c5, same final backend source): 2439 passed, 2 skipped, 0 failed. Backend was now running, so 12 external local-API tests also ran. Remaining skips are real Volcano SDK (no key) and PostgreSQL contract job. Existing datetime deprecations: 17 warnings.
- Frontend typecheck and lint passed; lint has no warnings/errors.
- Fresh-server full frontend Playwright: 290 passed, 21 skipped, 0 failed (311 total). Existing live/isolated-context skips remain, including four-chapter manifest-dependent cases; they are not claimed as verified. Relevant redirected chapter flow ran against the real local backend.
- Targeted backend path/upload regression: 66 passed. Billing under ambient fake=1: 9 passed. Model cleanup/text configuration: 42 passed.
- /tmp/avp-e2e/run_e2e_8000.sh: succeeded; pipeline a4845d41-eb4c-4814-b5fb-b237ed91b2fa. Initial run blocked only because the separate reference-image test service was absent; adding it resolved the smoke run.
- Code-health scan still reports 92 pre-existing blockers. Comparison with f2efccb8 found no newly blocked rule/file; this scan is NOT green and needs a separate cleanup effort.
- All test listeners on 8000/3000/3100/18081 and both worker processes were confirmed stopped after verification.

Logs: /Users/sunqinyue/Documents/avp-maint-20261106/
No live model/bucket test, no production guard relaxation, no large generated binary tracked, no PR, no stash/history rewrite. Existing unrelated untracked design documents were preserved.

All changes are local commits only. Remote push was not performed because the available owner message authorizes continuation but does not explicitly authorize publication of this new batch; the parent should obtain/verify that authorization before pushing the branch.
