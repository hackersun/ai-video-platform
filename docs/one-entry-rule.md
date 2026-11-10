# One-entry rule: route decisions (2026-11)

Every function has exactly one primary entry. Primary nav: 小说 · 任务中心 · 资产 · 成片 · 模型设置.
Everything else lives only under the 高级工具 menu (or is a contextual deep link, not a nav entry).

| Route | Decision | Why |
|---|---|---|
| `/quick-start` | Kept only under 高级工具. Home CTA "开始创作" now goes to `/novels` (canonical start). | Novel creation + one-click pipeline on `/novels` covers the beginner path; quick-start keeps the expert series-plan wizard. |
| `/producer` | Kept only under 高级工具. Contextual deep links from workflow/studio/novel chapter actions stay (they pass `workflow_id`). | Agent-style producer is an expert surface; the beginner path runs via the novel pipeline. |
| `/dashboard` | Kept only under 高级工具 as 数据概览. Login/register and workflow "back" now land on `/novels`. | Works list is the home; stats are secondary. |
| `/media-player` | No nav entry. Reached only as the playback link of a finished job. | Utility viewer, not a destination. |
| `/story-bibles` | Kept only under 高级工具 (故事设定). Preflight "fix" links stay contextual. | The novel page shows story-bible status; full editing is expert. |
| `/timelines` | Added under 高级工具 (时间线); was orphaned (no entry at all). | Manual timeline editing is expert-only; 成片 is the canonical output home. |

Models: chosen once in 模型设置 (global default) or per novel (novel page → 本小说单独设置).
Pages show a read-only "uses X" line with links to those two places; no per-page model dropdowns.
