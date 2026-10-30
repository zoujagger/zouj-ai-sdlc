---
name: retro
description: Retrospective with the playbook's leading and lagging metrics from git and GitHub, plus AI-workflow observations (CLAUDE.md, skills, hooks, evals). Use at the end of a sprint or period.
argument-hint: "[since date, e.g. 2026-10-01]"
---

# /zouj-ai-sdlc:retro

Period: since `$ARGUMENTS` (default: 14 days ago).

1. Compute from git, `.aiops/`, and `gh` (see `docs/governance.md`):
   - **Leading:** median intent-approved→spec-approved and spec-approved→plan-approved times (the `approved-at` stamps in `.aiops/*/`), % of PRs that link an intent, the eval pass rate on config changes, AI review findings per PR.
   - **Lagging:** rework after the build started (deviation-log entries, reopened PRs, follow-up fixes), change failure rate (reverts, hotfixes, rollbacks), MTTR from postmortems, lead time from intent to production.
2. Fill in `${CLAUDE_PLUGIN_ROOT}/templates/docs/retro.md` → `docs/retros/YYYY-MM-DD.md`.
3. Prompt the team for what went well and what didn't, plus **AI workflow observations**: repeated mistakes (→ `/zouj-ai-sdlc:learn`), noisy hooks (approval fatigue), stale CLAUDE.md, too many parallel sessions.
4. Propose at most 3 actions, including concrete `CLAUDE.md`, `.aiops/config/` or `REVIEW.md` changes where they'd help.
