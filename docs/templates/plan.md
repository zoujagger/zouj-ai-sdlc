---
id: NNNN
title: <Intent title>
status: Draft          # Draft | Accepted | In Progress | Done
engineer: <name who accepted the plan>
intent: ./intent.md
spec: ./spec.md
created: YYYY-MM-DD
---

# Plan: <Intent title>

<!-- Produced in Claude Code Plan mode from intent.md + spec.md, challenged by the engineer, then accepted.
     When code diverges from this plan, update this file IN THE SAME COMMIT (see Deviation log). -->

## Approach
<Short narrative of how the change will be built and why this order.>

## Stress test
<Questions the engineer asked to challenge the plan, with answers: failure modes, migration risk, test gaps.>

## Tasks
<!-- Status: [ ] todo · [~] in progress · [x] done. Each task leaves `make check` green and maps to AC IDs. -->
- [ ] **T1**: <imperative description>
  - AC: AC-1
  - Files: `src/...`
  - Tests: `tests/...`
  - Done when: <observable>
- [ ] **T2**: ...

## Parallelisation
<Which tasks can run in separate worktrees (max 2-3 sessions) without conflicts.>

## Verification
<How the verifier will confirm: commands, screenshots, evals.>

## Deviation log
| Date | Task | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
