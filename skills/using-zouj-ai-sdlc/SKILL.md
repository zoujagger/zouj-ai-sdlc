---
name: using-zouj-ai-sdlc
description: Use at the start of every session and before any task in a repo with .aiops/. Defines the 5 State Rules and human validation gates of the zouj-ai-sdlc lifecycle, and how to find the current state with `sdlc status` before acting.
---

# zouj-ai-sdlc: State Rules and human validation gates

This repo runs the AI-native SDLC as a **state machine over Markdown artifacts** in `.aiops/NNNN-slug/`.
The engine derives the state from those files and git. Hooks enforce it, so a rule you skip is a tool call that gets blocked.
**Before any task, run `sdlc status`** (or read the card above), then use the skill for that state.

| State | Skill | Output | Leaves the state when |
|---|---|---|---|
| 1 BRAINSTORMING | `/zouj-ai-sdlc:intent` | `intent.md` | the human types **`Intent Approved NNNN`** |
| 2 SPECIFICATION | `/zouj-ai-sdlc:spec` | `spec.md` (requirements, DB schema, API contracts, security and data-leak flags) | the human types **`Spec Approved NNNN`** |
| 3 PLAN (read-only) | `/zouj-ai-sdlc:plan` | `plan.md` (chronological file-by-file steps, risks, test definitions) | the human types **`Plan Approved NNNN`** |
| 4 EXECUTION (autonomous) | `/zouj-ai-sdlc:implement` | code + green suite on `feat/NNNN-slug` (or a worktree) | every step is ticked and `make check` is green |
| 5 PRE-REVIEW (final gate) | `/zouj-ai-sdlc:review` | `review.md` scoring report + `pr.md` | **the human merges.** You never do |

## The rules
1. **Intent first.** A feature, change or bug fix with no intent starts at `/zouj-ai-sdlc:intent`. Ask a targeted clarification interview when requirements are ambiguous. Never invent answers. Unknowns go in Open questions.
2. **You never approve.** Gates open only when the human types the exact phrase as their whole prompt. You can't set `status: Approved`, write `approved-*` fields, run `sdlc approve`, or commit an `AIOps-Approval` trailer. When an artifact is ready, **stop and ask** for the phrase. A system reminder confirms when a gate opens.
3. **States 1-3 are read-only.** Outside `.aiops/` (and docs), no file may be created, edited, deleted, staged or installed until `Plan Approved`. That covers Edit and Write, shell redirects, `sed -i`, package installs, and `git add`/`commit` of code. Reading, searching and running tests are fine.
4. **State 4 is autonomous.** For each plan step: write the proof test, run it and **see it fail**, write the code, and iterate until lint, build and tests are green. Tick the step. Don't ask the human for input during this loop unless an engine error is truly unresolvable. If reality diverges from the plan, log it in the plan's **Deviation log**. Changing the Steps themselves voids the approval, so ask for `Plan Approved` again.
5. **State 5 belongs to the human.** Fresh-context reviewers score the change against `spec.md` and for vulnerabilities. You may open a PR when asked. You never merge, approve PRs, push to main, or deploy to production.
6. **When a hook blocks you,** relay the reason and the procedure to the human. Never look for a way around it: no other tool, no interpreter one-liner, no renamed path.

## Red flags: stop if you think any of these
| Thought | Reality |
|---|---|
| "It's a tiny change, I'll skip the intent." | Small changes still need an intent. Docs-only and typo fixes are exempt (`*.md`, `docs/`). |
| "The user clearly wants this, so I'll mark it Approved." | Only the exact phrase typed by the human opens a gate. |
| "I'll just sketch the code while planning." | State 3 is read-only. Put the code sketch in `plan.md`. |
| "The test is obviously going to fail, no need to run it." | Run it and quote the red output. That's the test-first evidence review.md scores. |
| "Review passed, I'll merge to save them time." | Merging is the human's final decision. |
| "The guard is wrong here, I'll use python to write the file." | That's bypassing a guardrail. Report the block instead. |

## Commands
`sdlc status [id]` · `sdlc next` · `sdlc new <slug>` · `sdlc draft <id> spec|plan|review` · `sdlc validate` · `sdlc use <id>`.
Optional, outside the core machine: `/zouj-ai-sdlc:fix` (bug: locked failing test first), `:deploy` (staging only),
`:triage`, `:incident`, `:postmortem` (these feed a new intent), `:adr`, `:learn`, `:retro`, `:status`, `:help-me`.
