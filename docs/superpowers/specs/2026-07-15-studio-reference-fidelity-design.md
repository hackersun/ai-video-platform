# Studio Reference Fidelity Design

## Intent

Match the user-supplied Studio production-board screenshot at the information-architecture and visual-density level while keeping every displayed value traceable to current frontend data or an existing API.

## Visual Contract

- Keep the page title compact; the large mode banner must not compete with the series summary.
- Render a wide series summary containing cover state, title, progress, completed episode count, total chapter count, update time, and series-asset readiness.
- Render episode cards with chapter identity, workflow-step progress, current/active state, a new-episode entry, and series management.
- Render a board header with current episode, total shots, completed shots, pending/warning count, duration, episode-info entry, and review entry.
- Render four dense production columns. Cards expose concrete evidence such as entity counts, lock coverage, shot/video/TTS/subtitle counts, model hint, shot warnings, consistency score, and synthesis output.
- Render a right rail for real cost state, aggregate model readiness, and blockers/failed jobs.
- Render a full-width bottom command bar with secondary recovery/navigation and the primary recommended action.

## Truthfulness Rules

- Use `Novel.cover_url` only when present. A missing cover is explicitly labelled and never replaced with unrelated artwork.
- Use workflow `completed_steps`, `current_step`, job id arrays, and chapter titles for episode cards; do not synthesize production completion.
- Use shot/job/quality report data for the board. Do not assign fictional owners or models.
- When cost totals are unavailable, render `暂无费用记录` and a link to the existing analytics surface; do not estimate currency.
- Keep production/test mode switching accessible in the command area and preserve all confirmation and safety behavior.

## Responsive Contract

- Desktop at 1440 x 1024 follows the source proportions: main board plus a narrow right rail and an above-fold command bar.
- Mobile at 390 x 844 stacks summary, episodes, board columns, rail, and command actions with no horizontal overflow.

## Acceptance

- The source screenshot and current implementation are compared in one normalized image.
- No actionable P0/P1/P2 mismatch remains.
- Existing multi-episode switching, model response compatibility, guided actions, retry/recovery, and expert tools remain functional.
- Focused E2E, typecheck, production build, and real four-chapter browser validation pass.
