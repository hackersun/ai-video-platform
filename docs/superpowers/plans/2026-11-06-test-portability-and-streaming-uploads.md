# Test portability and bounded uploads implementation plan

**Goal:** Finish the five approved maintenance items without live API keys, buckets, new UI pages, weakened gates or history rewriting.
**Architecture:** Keep existing routes and responses. Test fixtures own synthetic media; shared bounded-copy helpers own upload byte accounting and cleanup. Cloud adapters stream existing local files.
**Constraints:** Work on the existing Mac branch, preserve unrelated untracked design documents; Python backend/venv/bin/python. Never stash/rewrite history/open a PR. No live provider calls.

## Tasks and verification
- [x] Update four-chapter creation helper to derive ID from the detail-page redirect; test with fresh Playwright server.
- [x] Remove billing's duplicate ambient-environment fixture; run billing tests with fake mode exported.
- [x] Share cleanup of legacy LLMConfig and user-default model-center bindings; add a regression proving stale binding removal and user isolation.
- [x] Identify file-reading tests that rely on untracked generated media, generate tiny images/audio/video in test setup, clean only created files; verify backend tests in a fresh local clone under /tmp. Correct only the path-dependent test expectation (keep runtime guard unchanged).
- [x] Add bounded async upload copy with partial-file removal; stream asset and voice uploads, bound novel parsing; stream S3 PUT and Qiniu multipart without buffering entire files. Add tests for bounded reads, limits, empty/disconnected uploads and adapter streams.

## Final acceptance
Run backend full suite (test_*.py plus tests/) in the workspace and clean clone; frontend typecheck, lint and all Playwright tests with no old frontend; /tmp/avp-e2e/run_e2e_8000.sh must succeed. Record actual counts and skips. Shut down only related test servers/workers on ports 8000/3000/3100/18081 after verification. Commit each independent change; remote publication requires explicit user authorization.
