---
name: parallel
description: Runs 2-3 independent plan.md steps of an approved plan in parallel git worktrees (state 4). Use when plan steps touch disjoint files and the human wants them done concurrently.
argument-hint: "<intent-id> <steps, e.g. S2 S3>"
disable-model-invocation: true
---

# Parallel worktrees (state 4 only)

1. `sdlc status <id>` must show state 4. Refuse more than 3 sessions in total: parallel work nobody can review is the bottleneck, not throughput.
2. Check that the steps' `Files:` don't overlap. If they do, run the steps in sequence instead.
3. For each step, run `sdlc-worktree <id> <step>`. It creates `../<repo>-<id>-<step>` on branch `feat/<id>-<step>`, and since the branch carries the intent id, the worktree is active and unlocked.
4. Print, for each one: `cd <path> && claude "/zouj-ai-sdlc:implement <id> <step>"`.
5. Remind the human that each branch merges back into `feat/<id>-…` (never into main) and that ticks and deviations land in that branch's plan.md.
