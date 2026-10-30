---
id: NNNN
title: <Title>
status: Draft          # Draft → Approved (human types `Plan Approved NNNN`: unlocks code)
spec: ./spec.md
created: YYYY-MM-DD
---

# Plan: <Title>

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
<Short narrative: how the change will be built and why in this order. Existing code to reuse (path:line).>

## Steps
- [ ] **S1**: <imperative description>
  - Files: `src/...` (create | modify)
  - Test first: `tests/...` → <what fails before the change>
  - Covers: AC-1

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|

## Test definitions
<!-- One row per acceptance criterion, at least. -->
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/...::test_...` | unit | <observable behaviour> |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
