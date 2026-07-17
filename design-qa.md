# Asset Workbench Design QA

- Date: 2026-07-15
- Route: `http://localhost:3000/assets`
- Reference: `/Users/sunqinyue/.codex/generated_images/019f4ca9-c6c3-7701-9e09-0cf4fc148093/exec-cffc50a5-4724-423d-8009-04abfc814117.png`
- Browser evidence: `/tmp/asset-workbench-final-2026-07-15.png`
- Side-by-side comparison: `/tmp/asset-workbench-comparison-2026-07-15.png`

## Visual review

- Information hierarchy matches the selected direction: compact workbench header, smart collections, dense asset table, persistent inspector, and contextual bulk bar.
- Existing navigation, dark violet visual language, typography, border treatment, and Lucide icon system remain consistent with the product.
- Asset thumbnails keep their natural ratio without stretching; missing media uses the existing icon treatment.
- Desktop layout was checked at 1272 x 716. The table, inspector, filters, and primary actions remain readable without clipping.
- Mobile layout was checked at 390 x 844 by automated browser acceptance; document overflow is zero.

## Interaction review

- Created a new reference asset from the frontend and confirmed it appeared in the workbench.
- Filtered the real catalog to the character collection and confirmed counts and rows updated.
- Selected an asset and confirmed the sticky bulk bar appeared.
- Ran bulk lock from the frontend and confirmed smart collection counts, row status, and inspector action updated to the locked state.
- Existing edit, history backfill, regeneration, and production-card missing-view completion tests remain green.

## Verification

- `npx playwright test e2e/assets-workbench-redesign.spec.ts --project=chromium --workers=1` — 2 passed.
- `npx playwright test e2e/assets-low-barrier-management.spec.ts --project=chromium --workers=1` — 2 passed.
- `npm run build` — compiled successfully and passed type validation.

final result: passed

---

# Studio Reference Fidelity QA

- Date: 2026-07-15
- Route: `http://localhost:3000/studio?workflow_id=6fd7489f-8b7e-42f2-8144-89fb22fdb331`
- Source visual truth: `/var/folders/n8/ycr1x81x0pg3f6nxgj6tcc080000gn/T/codex-clipboard-472a5236-de4e-485e-b8fe-cf1dd53fd539.png`
- Implementation screenshot: `/tmp/studio-detail-real-final.png`
- Mobile screenshot: `/tmp/studio-detail-real-mobile.png`
- Full-view comparison evidence: `/tmp/studio-detail-design-compare-final.png`
- Focused board comparison: `/tmp/studio-detail-design-focus-board.png`
- Viewport: requested desktop 1487 x 1058 (browser content capture 1479 x 1052); mobile 390 x 844
- State: authenticated `sunqy` user, production mode, real four-chapter novel, fourth chapter active

## Findings

- No actionable P0, P1, or P2 differences remain after the final comparison.
- Typography: page, series, board, and lane headings now use the source's stronger hierarchy; real long novel names truncate rather than pushing metrics or actions out of alignment.
- Spacing and layout rhythm: the desktop content spans 1415 px with 32 px page margins, the 1169 px board and 230 px status rail align vertically, and the 78 px command bar ends at y=1043.5 inside the requested 1058 px viewport.
- Colors and visual tokens: the existing navy surface, violet primary state, cyan section accents, and emerald/amber/red status colors map closely to the source while preserving the shipped design system.
- Image quality and asset fidelity: the real novel has no `cover_url`, so the truthful empty-cover state remains. The source's cover, people thumbnails, owner avatars, and spend amount were not recreated with placeholders because the current snapshot does not provide those assets or values.
- Copy and content: all chapter names, episode counts, model readiness, warnings, task counts, consistency scores, durations, and actions come from the real four-chapter workflow. Test/production mode controls remain intentionally visible because they are part of the product's safety contract.
- Responsive behavior: at 390 x 844, `scrollWidth - innerWidth = -8`; the series summary and episode cards stack without horizontal clipping.

## Full-view and focused evidence

- The normalized full-view comparison shows the same macro composition: compact title, series summary, one-row episode strip, four-lane production board, top-aligned right status rail, and a full-width bottom command bar.
- The focused board comparison confirms lane dividers, heading rhythm, status cards, warning emphasis, inline repair actions, and the board-to-command transition at readable scale.
- The right rail was judged in the full-view comparison because its complete outer container and three nested status cards remain legible there.

## Comparison history

1. Initial comparison (`/tmp/studio-detail-gap-before.png`) found P1 structural drift: the old workbench lacked the reference's series summary, episode strip, board header, detailed four-lane evidence, aligned status rail, and dual-action command area.
2. First implementation (`/tmp/studio-detail-real-after-1.png`) fixed the missing structure but retained P2 differences: the status rail began at board level, episode actions stacked, the cover slot was undersized, and the command bar fell below the fold.
3. Second iteration (`/tmp/studio-detail-real-after-wide.png`) aligned the rail with the series summary and restored the single-row episode strip, but a 1232 px content cap and per-lane footer buttons still made the board too narrow and tall.
4. Final fixes introduced a Studio-only wide layout, moved lane actions into their relevant cards, compacted the command controls into one horizontal bar, added the rail's outer container, and tightened heading typography.
5. Post-fix evidence (`/tmp/studio-detail-design-compare-final.png` and `/tmp/studio-detail-design-focus-board.png`) shows no remaining actionable P0/P1/P2 mismatch. Remaining visual differences are expected data differences or intentional safety controls.

## Interaction and runtime evidence

- Switched from the fourth episode to the first episode and back from the rendered episode strip; each selected workflow loaded the correct chapter board.
- Switched to test validation and back to production mode; both controls resolved uniquely and displayed their active semantic state.
- Final desktop browser console error count: 0.
- Final desktop horizontal overflow: -8 px; command bar bottom: 1043.5 px.
- Mobile horizontal overflow: -8 px.

## Follow-up polish

- P3: when the backend supplies a real cover, accountable spend rows, owner assignments, or shot thumbnails, these slots can become visually richer without changing the current layout.

final result: passed

---

# Studio Episode Board Design QA

- Date: 2026-07-15
- Route: `http://localhost:3000/studio?workflow_id=6fd7489f-8b7e-42f2-8144-89fb22fdb331`
- Source visual truth: `/Users/sunqinyue/.codex/generated_images/019f4ca9-c6c3-7701-9e09-0cf4fc148093/exec-243b7cc9-5996-47fd-bea0-4fd2c2c03313.png`
- Implementation screenshot: `/tmp/studio-v2-four-chapter-desktop-final.png`
- Mobile screenshot: `/tmp/studio-v2-four-chapter-mobile.png`
- Full-view comparison evidence: `/tmp/studio-v2-design-compare-final.png`
- Viewport: desktop 1440 x 1024; mobile 390 x 844
- State: authenticated `sunqy` user, production mode, real four-chapter novel workflow, fourth-chapter snapshot active

## Findings

- No actionable P0, P1, or P2 differences remain.
- Typography: the existing product font stack, weights, truncation, and compact UI hierarchy are retained; long real novel and workflow names truncate without displacing controls.
- Spacing and layout: the episode strip, four production lanes, status rail, and primary command bar follow the selected episode-first composition. The command bar remains above the desktop fold.
- Colors and tokens: existing navy, violet, cyan, emerald, amber, and red semantic tokens are used consistently with the source direction and the shipped design system.
- Image quality: the real snapshot has no cover image or cost payload, so the implementation intentionally omits the source mock's cover and spend card instead of inventing assets or values.
- Copy and content: labels use real workflow, chapter, readiness, model-contract, blocker, job, and consistency data. Production/test mode language preserves the existing safety gate.
- Responsive behavior: the 390 px viewport reports `scrollWidth = clientWidth = 382`; no horizontal overflow is present.

## Focused region review

A separate focused crop was not needed: the normalized 2880 x 1024 side-by-side comparison keeps the episode strip, lane cards, model states, blockers, and primary command bar legible at original detail. The mobile screenshot separately verifies the narrow layout and wrapping behavior.

## Comparison history

1. First comparison found a P2 layout issue: the primary next-action command bar waited for the taller right rail and fell below the 1024 px desktop fold.
2. Fix: grouped the four-lane board and command bar in the main grid column while keeping the status rail independent.
3. Post-fix evidence: `/tmp/studio-v2-design-compare-final.png` shows the command bar directly below the lanes, matching the source composition and restoring above-the-fold visibility.

## Interaction and runtime evidence

- Real workflow filtering shows exactly four same-novel episode buttons; unrelated workflows and duplicate chapter entries are excluded.
- The series-management menu exposes the existing production-card entry.
- Final browser state contains no visible fetch error; the transient snapshot failure was recovered through the existing `重新加载工作台` action.
- Final mobile and desktop captures show no relevant console error state.

## Follow-up polish

- P3: when the API has no series plan, episode numbering still follows the filtered workflow order. A future backend chapter-order field would make fallback numbering semantically exact without title parsing.

final result: passed
