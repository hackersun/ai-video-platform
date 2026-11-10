# Reproducible test media

## Fixture audit
`backend/static/generated` is runtime output, not source. A clean local clone at f2efccb8 completed 2411 backend tests with no missing-media failures; the sole failure was a test incorrectly assuming the default relative SQLite path is always outside /tmp. The runtime database guard is unchanged; the test now checks the resolved location.

Backend image persistence tests already generate images with Pillow or in-memory bytes; FFmpeg renderer tests synthesize temporary clips. Deterministic fake generation creates /static/dev outputs on demand; the reference service generates its image response. Keep these isolated from real cloud providers.

Mocked browser specs assets-workbench-redesign, novel-detail-overview and producer-batch-evidence had hard-coded generated image URLs without image responses. They now opt into helpers/synthetic-media.ts, which constructs a valid tiny PNG in memory. studio-smart-console already supplies its own image mock. Real four-chapter and publication runs do not use the mock fixture. Video URL-only mocks do not read repository files.

Regression: the asset thumbnail must actually decode (naturalWidth > 0), not merely exist in the DOM. No media binaries are added to git.


## Verification environment
Use backend/venv/bin/python, and run pytest from backend/ so test_*.py and tests/ are both collected. Full browser tests include live-local API cases (assets.spec.ts and comprehensive.spec.ts), so start the deterministic backend before running them. Set PLAYWRIGHT_REUSE_EXISTING_SERVER=0 and ensure 3100 is free. The shared synthetic-image fixture applies only to opted-in mocked UI specs.

The existing /tmp/avp-e2e/serve.sh starts the backend and workers, but the deterministic reference image service also needs to be listening on 18081: `cd backend && venv/bin/python scripts/serve_deterministic_reference.py --port 18081`. Its image is `/valid-composite.png`. The smoke script blocks at reference_preparation_blocked without that service. Stop these test processes when finished.

The comprehensive chapter-creation test had the same obsolete list-page assumption as the four-chapter helper. It now follows the detail URL, explicitly opens the chapters tab, submits the current dialog and asserts a persisted chapter link instead of silently skipping a missing button.
