# CLAUDE.md

This repo uses the **zouj-ai-sdlc** plugin: a 5-state machine over Markdown artifacts in `.aiops/NNNN-slug/`.
Run `sdlc status` before any task. The plugin's hooks enforce the rules below, and every block states the procedure.

| State | Skill | Artifact | Human gate |
|---|---|---|---|
| 1 BRAINSTORMING | `/zouj-ai-sdlc:intent` | intent.md | `Intent Approved NNNN` |
| 2 SPECIFICATION | `/zouj-ai-sdlc:spec` | spec.md | `Spec Approved NNNN` |
| 3 PLAN (read-only) | `/zouj-ai-sdlc:plan` | plan.md | `Plan Approved NNNN` |
| 4 EXECUTION (autonomous TDD) | `/zouj-ai-sdlc:implement` | code + tests | none (`make check` green) |
| 5 PRE-REVIEW | `/zouj-ai-sdlc:review` | review.md, pr.md | the human merges |

## Rules
- Gates open only when a human types the approval phrase as the whole prompt. Agents never approve, merge or deploy to prod.
- Code is read-only until `Plan Approved`. Docs (`*.md`, `docs/`) are exempt.
- Bug fixes: `/zouj-ai-sdlc:fix` (failing test first, then `sdlc lock`).
- Commits: Conventional Commits + `Refs: .aiops/NNNN-slug`. Branches: `feat/NNNN-slug`, `fix/NNNN-slug`.

## Commands
`make format` · `make lint` · `make typecheck` · `make test` · `make build` · `make check` · `make deploy ENV=staging`

## Lessons
<!-- One imperative line per recurring mistake (/zouj-ai-sdlc:learn). -->

## Project notes
<!-- Stack, architecture, gotchas. Keep this file to about a page. -->
