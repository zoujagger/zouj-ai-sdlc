# CLAUDE.md

This repo follows Anthropic's **AI-native SDLC**. Work starts from an **intent**, every stage commits an artifact the next stage reads,
and humans decide at every gate. Workflow: @docs/sdlc.md · Review rules: @REVIEW.md · Governance: @docs/governance.md

## The loop
**Intent → Plan → Design → Build → Test → Deploy → Maintain → (new intent)**
`/intent` → `/spec` → `/plan` (Plan mode) → `/implement` → `/verify` → `/review` → `/pr` → `/deploy` → `/triage`
Lost? `/sdlc <id>`. Artifacts live in `docs/intents/NNNN-slug/`: `intent.md` → `spec.md` → `plan.md`.

## Rules
1. **Intent first.** No spec without a validated `intent.md`. No code without an accepted `spec.md` and `plan.md`.
   Exempt: typos, docs-only, dependency bumps.
2. **Plan mode before building.** The engineer challenges and accepts the plan, and it's committed as `plan.md`.
3. **When code diverges from `plan.md`, update `plan.md` (tasks + Deviation log) in the same commit.**
4. **Bug fixes:** failing test first, human approves it, tests get locked (`/fix`), then fix the code. Never edit locked tests.
5. **Stop at the production gate.** Deploy to staging, then hand off. Never deploy to prod, merge PRs, or approve your own work.
6. **Never bypass guardrails.** If a hook blocks you, explain the reason and the procedure, and ask the human.
7. Don't invent requirements. Unknowns go in "Open questions".

## Definition of done
- `make check` is green (the Stop hook enforces this) and every AC in `spec.md` has a test that would fail without the change.
- `plan.md` tasks are ticked, and any deviations are logged.
- `/verify` (fresh-context verifier) says VERIFIED. UI changes include a screenshot.
- Docs and `CHANGELOG.md` `[Unreleased]` are updated.

## Commands (configure in `Makefile`)
`make format` · `make lint` · `make typecheck` · `make test` · `make build` · `make check` (= lint+typecheck+test)
`make deploy ENV=staging` · `make rollback ENV=staging` · `make evals` · `make validate-template`

## Working style
- **Auto mode** is fine for routine, well-tested tasks. Review the artifacts at the end of the session.
- **Parallelism:** at most 2-3 sessions, each in its own worktree (`/parallel`). Delegate repetitive work to subagents.
- Commits: Conventional Commits + `Refs: docs/intents/NNNN-slug`. Branches: `feat/NNNN-slug`, `fix/...`.
- Cite code as `path:line`.

## Lessons
<!-- When Claude makes the same mistake twice, add a one-line rule here (use /learn) and add an eval. Keep this file about one page. -->

## Project notes
<!-- Stack, architecture overview, key modules, gotchas. -->
