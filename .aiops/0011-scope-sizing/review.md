---
id: 0011
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 60c1e4cb1a72ee6358db83737c60998be17befdb
score: 93/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-20
---

# Review: Scope sizing: cap acceptance criteria per intent

<!-- State 5 PRE-REVIEW. Written from the report of one fresh-context reviewer covering the three personas, who got
     only the intent folder and the base branch `main` (a92936e). -->

## Summary
- **Validator:** a new `scope_size` check on spec.md counts the distinct AC ids in `## Acceptance criteria`. More
  than 5 is a warning that suggests a split. More than 8 is an error while the spec's gate is closed, so `approve`
  refuses an oversized Draft spec. Approved specs only warn.
- **Advice:** the intent and spec skills, product-analyst and both templates carry the scope-split check, the 3-5
  caps and the **Scope:** callout.

No gate, hash, approval, lock or audit path changes. **PASS, 93/100**: every AC is met, and there is no BLOCKER and
no CRITICAL/HIGH finding.

The reviewer ran:
- `pytest test_engine.py::ScopeSizing test_cli.py -k "ScopeSizing or scope or Docs or changelog"`: 22 passed;
- `bin/sdlc validate --all`: 0 errors, the warning on 0001-0010.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_engine.py::ScopeSizing::test_five_or_fewer_is_quiet` (2 and 5 ACs), `::test_counts_distinct_ids_in_the_section` (a repeated id, ids in a comment, ids outside the section); `lib/sdlc_engine/schema.py:85` via `A.ac_ids` (`artifacts.py:91`) |
| AC-2 | ✅ met | `ScopeSizing::test_six_to_eight_warn` (6 and 8), `tests/test_cli.py::Lifecycle::test_validate_scope_size_exit_codes` (exit 0, `! … has 6 criteria`); the R-3 text at `schema.py:94-97` matches the spec |
| AC-3 | ✅ met | `::test_nine_draft_is_an_error` (the exact R-4 string, no warning), `::test_nine_stale_is_an_error`, `::test_approved_eight_plus_ninth_is_stale` (a real `approve`, then a ninth AC: error, back to state 2), `::test_approve_refuses_nine`, and the CLI test (exit 1, `✗ … Spec exceeds maximum of 8`); the R-4 text at `schema.py:89-92`; the refusal comes from `approvals.py:251` |
| AC-4 | ✅ met | `::test_nine_approved_only_warns`, `::test_this_repos_specs_have_no_scope_error`; `sdlc validate --all`: 0 errors |
| AC-5 | ✅ met | `tests/test_cli.py::Docs::test_scope_sizing_guidance` checks the intent skill (step 3 scope check, step 4 caps and callout), the spec skill (step 3, the step 6 5/8 rule), product-analyst (Intent cap, Strict cap, behavioural ACs, the callout) and both templates; `make check` 524 OK (Deviation log, S3) |

## Security
None found.
- The check can only add errors or warnings. Whether the gate is open is judged from `status` and
  `approved-sha256`, which the pre-edit guard keeps the agent from writing. Forging them would already open the gate
  itself, which the signed CI audit catches, so the check adds no new route.
- The spec's "no override" flag holds: there is no config key, and `allowed-commands` is read only by heuristic bash
  rules.
- This repo's `--ci` runs the base branch's engine, so the head's check can't weaken the audit.

## Plan conformance
- S1, S2 and S3 match the plan file by file. All nine named S1 tests and the CLI test exist, and
  `git diff --name-only main...HEAD` lists only the S1 and S2 files and `.aiops/0011-*`.
- **Deviation 1 (S2) is accurate and justified.** 0010's assertion that `[Unreleased]` holds no `### ` could hold
  only at a release commit, and R-8's CHANGELOG entry fails it. The beta.2 section checks remain. Lost: a release-time
  check that `[Unreleased]` was emptied into the release.
- **Deviation 2 (S3) fairly explains the eval.** `intent-first` scored 0.89 with the plugin (1 / 0.67 / 1) against
  1.00 without. With-run 2 failed with `OSError: [Errno 30] Read-only file system` from `sdlc new` in the sandbox;
  the agent stopped and reported it. It was a sandbox fault, not the scope check, and no run stopped at the scope
  check.

## Test-first evidence
- **S1, 0a84667:** the tests and `schema.py` are in one commit, so the history holds no red commit. The reviewer
  found the plan's red description credible (before S1 no `scope_size` existed), but its replay in a scratch copy
  was refused, so it didn't confirm the red run itself. The implementing session recorded it before the change:
  `7 failed, 3 passed`. The 3 that passed are the planned false-positive guards (`test_five_or_fewer_is_quiet`,
  `test_counts_distinct_ids_in_the_section`, `test_this_repos_specs_have_no_scope_error`). The failures were, for
  example, `test_validate_scope_size_exit_codes`: `'! … has 6 criteria' not found in 'validate: 1 intent(s), 0
  artifact(s) with errors'`.
- **S2, 26968c4:** `Docs::test_scope_sizing_guidance` ran red first (`'Scope check' not found` in step 3) and fails
  without the text changes.
- **S3, 60c1e4c:** the verification itself.

## Backlog (not blocking)
1. `test_six_to_eight_warn` and `test_nine_approved_only_warns` assert only parts of the R-3 warning; assert the
   full string, as for R-4.
2. Make the check protocol explicit (always `(errors, warnings)`, or a small named type) instead of
   `isinstance(tuple)`, which would misread a check that returns a tuple of errors.
3. Share one gate helper with `machine.gate()` (it also compares `id` with the folder), so the two can't drift.
   Today `validate()` already errors on an id mismatch.
4. The count can be dodged: several criteria under one id, or `AC-01` beside `AC-1`. It's advice-level; the human
   reviews the spec.
5. The Deviation log's Commit column says "S2"/"S3" rather than shas (26968c4, 60c1e4c).
6. AC-3's approval refusal is tested through `approvals.approve()` only (the CLI refuses under the agent anyway),
   and the stale path has no CLI exit-code test.
7. `docs/demo/demo.tape` has an unrelated uncommitted change in the working tree; keep it out of the PR.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | every AC met; the warning text is asserted only in part |
| Security | 25 | 25 | none found; no gate or audit path touched |
| Test quality & test-first | 20 | 17 | the red run sits in the session, not in a separate commit |
| Plan conformance | 10 | 9 | deviations accurate; the Commit column holds step ids, not shas |
| Maintainability | 5 | 4 | the tuple-or-list check protocol is implicit |
| **Total** | 100 | **93** | PASS needs ≥ 80, no BLOCKER, every AC met |
