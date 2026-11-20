---
id: 0011
title: Scope sizing: cap acceptance criteria per intent
status: Approved
spec: ./spec.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T14:18:16Z
approved-via: cli
approved-sha256: af521ce6d2d7347daf2f70558234d04e5a2ae22de13cfb7902f63dc123734e48
---

# Plan: Scope sizing: cap acceptance criteria per intent

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Three steps. The engine comes first and test-first (CLAUDE.md rule 2), then the advice text with its own test, then
the verification.

1. **S1, the validator.** The new check needs the raw text: the gate test hashes it, and `A.Artifact` holds only the
   front matter and the body (`artifacts.py:20-42`). So `validate()` (`schema.py:36-37`) calls each check as
   `CHECKS[name](d, a, secs, text)`. The four existing checks take a `text` parameter they don't use. The new
   `_scope_size` returns `(errors, warnings)`, and `validate()` accepts a list or a tuple (spec R-6).
   - It counts `A.ac_ids(secs.get("Acceptance criteria", ""))`, which already drops HTML comments and counts each
     distinct id once (`artifacts.py:91`).
   - The gate test copies `machine.gate()` (`machine.py:145-150`) on the given text:
     `a.get("status") == SCHEMAS["spec"]["gate"] and a.get("approved-sha256") == A.approval_hash("spec", text)`.
   - It reaches `approve` without new code: `approvals.py:251` refuses an artifact whose `validate()` has errors.
2. **S2, the advice.** A `Docs`-style test (`tests/test_cli.py:929`) checks the key phrases in the shipped
   text, then the skills, the agent, the templates and the docs change to match.
3. **S3, the checks.** `make check`, `make validate`, `sdlc validate --all` on this repo, and one run of the
   `intent-first` eval, since the intent skill changed.

**Test fixtures.** The tests build specs with N ACs from `helpers.SPEC` (2 ACs) by replacing its AC block. An
approved, unchanged spec with 9 ACs can't come from `approve` (it validates first), so that test writes
`status: Approved` and `approved-sha256: A.approval_hash("spec", text)` itself. The gate only compares the hash.
A second test takes the real path: `approve` an 8-AC spec, add a ninth AC, and see the error.

**Answers from the plan review (zoujagger, 2026-11-20):** run the `intent-first` eval in S3; keep the repo-specs
test in S1 so CI guards `.aiops/`; keep the direct fixture and add the approve-then-edit test.

## Steps
- [x] **S1**: Count spec ACs in `sdlc validate`: warn above 5, error above 8 while the gate is closed.
  - **Files:**
    - `tests/test_engine.py` (modify): a new class `ScopeSizing(RepoCase)` with a helper `spec_with(n, approved=False,
      stale=False)`. Its tests:
      - `test_five_or_fewer_is_quiet`: 2 and 5 ACs give no scope warning or error (AC-1);
      - `test_six_to_eight_warn`: 6 and 8 ACs give one warning naming the count and "splitting", and no error
        (AC-2);
      - `test_nine_draft_is_an_error`: 9 ACs in a Draft give exactly
        `Spec exceeds maximum of 8 acceptance criteria; consolidate behavioral outcomes or split into smaller
        intents. (spec.md has 9.)`, and no scope warning (AC-3);
      - `test_nine_stale_is_an_error`: `status: Approved` with a hash that doesn't match gives the same error (AC-3);
      - `test_approved_eight_plus_ninth_is_stale`: with the intent approved, `approve` an 8-AC spec (it validates,
        with the warning), then append `- **AC-9**: …` to `## Acceptance criteria`. `validate()` now gives the error,
        and the gate is closed (AC-3);
      - `test_approve_refuses_nine`: with the intent approved, `approvals.approve(…, "spec")` returns False and names
        the error (AC-3);
      - `test_nine_approved_only_warns`: an approved spec with a matching hash gets the warning and no error
        (AC-4);
      - `test_counts_distinct_ids_in_the_section`: an id repeated in the section, ids in an HTML comment, and ids
        outside `## Acceptance criteria` don't count (R-1);
      - `test_this_repos_specs_have_no_scope_error`: every `ROOT/.aiops/*/spec.md` validates with no "exceeds
        maximum" error (AC-4).
    - `tests/test_cli.py` (modify): `test_validate_scope_size_exit_codes`: `sdlc validate` exits 0 with a `! …
      spec.md: … has 6 criteria` line, and exits 1 with a `✗ … Spec exceeds maximum of 8` line for 9 (AC-2, AC-3).
    - `lib/sdlc_engine/schema.py` (modify): `WARN_ACS = 5`, `MAX_ACS = 8`, `_scope_size`, `"scope_size"` in
      `CHECKS`. The check call passes `text`, and a tuple result is split into errors and warnings. The four existing
      checks take `text`.
    - `schemas/spec.json` (modify): `"checks": ["has_acceptance_criteria", "scope_size"]`.
  - **Test first:** the new tests fail. The 6-AC test finds no warning, and the 9-AC Draft test finds no error.
    `test_five_or_fewer_is_quiet` and the repo test pass from the start: they guard against false positives.
  - Covers: AC-1, AC-2, AC-3, AC-4
- [ ] **S2**: Write the sizing advice into the skills, the agent, the templates and the docs.
  - **Files:**
    - `tests/test_cli.py` (modify): `Docs::test_scope_sizing_guidance` asserts that:
      - `skills/intent/SKILL.md` has "Scope check" in step 3, before step 4's `sdlc new`, and "3 to 5" outcomes in
        step 4;
      - `skills/spec/SKILL.md` has "3 to 5" ACs and the 5/8 rule;
      - `agents/product-analyst.md` has "Intent cap", "Strict cap", "never more than 7", "user-observable" and the
        "Scope:" callout;
      - `templates/artifacts/intent.md` has "3 to 5" and the "Scope:" callout, and `templates/artifacts/spec.md`
        has "3 to 5".
    - `skills/intent/SKILL.md` (modify): the step 3 **Scope check** (several workflows, or more than 5 outcomes or
      ACs → AskUserQuestion: split into smaller intents, before step 4), and step 4's delegation with the caps and
      the callout rule. A red-flag row: "Packing an epic into one intent" → split.
    - `skills/spec/SKILL.md` (modify): step 3 asks product-analyst for 3 to 5 concise, user-observable ACs, with the
      technical detail moved to Requirements, Data model and API contracts. Step 6 names the 5/8 rule.
    - `agents/product-analyst.md` (modify): the Intent cap and the scope-split check in State 1; the Strict cap,
      the behavioural rule and the epic callout (`> ⚠️ **Scope:** …`) in State 2 and Rules.
    - `templates/artifacts/intent.md` (modify): the comment under `## Desired outcome` names the 3-to-5 cap, and
      the header comment names the callout.
    - `templates/artifacts/spec.md` (modify): the AC comment names the 3-to-5 target and the 5/8 rule.
    - `docs/state-machine.md` (modify): a `scope_size` row in the Schemas table.
    - `CHANGELOG.md` (modify): `[Unreleased]` → `### Added` entry naming `.aiops/0011-scope-sizing/`.
  - **Test first:** `test_scope_sizing_guidance` fails on the missing phrases.
  - Covers: AC-5
- [ ] **S3**: Prove the change.
  - **Commands:**
    - `make check`;
    - `make validate`;
    - `bin/sdlc validate --all` (0001-0011: no errors, warnings for the oversized approved specs);
    - `git diff --name-only main`: only the files S1 and S2 name, and `.aiops/0011-*`;
    - one run of the `intent-first` eval (`claude plugin eval . --scaffold --trust-plugin --allow-tools Bash Write
      Edit --no-publish --case intent-first --runs 3 --max-cost-usd 3`, about $0.80).
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-4, AC-5

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Anaconda's `ruff` 0.15.1 is on PATH. If the session runs with the plugin's hooks, `make format` reformats lib/ and tests/ on every edit | high if the hooks load | high: a 5k-line diff, broken lint | Check `git status` after each edit. Restore any file the step doesn't name with `git checkout --`. Or restart the session with ruff off PATH |
| CI lint (shellcheck, ruff 0.6.9) catches what local lint doesn't (unused variables) | medium | low: a red PR | No shell changes. Check `lib/` for unused names by hand, and watch `gh pr checks` |
| The new check fires on an existing spec | low | high: CI red | `test_this_repos_specs_have_no_scope_error`, plus `sdlc validate --all` in S3 |
| Phrase tests make the docs brittle | medium | low | Assert a few key phrases, not whole sentences |
| The scope check makes the agent stop and ask during the non-interactive `intent-first` eval | low | medium: eval score drops | The eval's CSV export fits in 5 outcomes. If it drops, log it and revise the wording before review |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_engine.py::ScopeSizing::test_five_or_fewer_is_quiet`, `::test_counts_distinct_ids_in_the_section` | unit | ≤ 5 distinct ids in the section: no scope message |
| AC-2 | `tests/test_engine.py::ScopeSizing::test_six_to_eight_warn`, `tests/test_cli.py::…::test_validate_scope_size_exit_codes` | unit, CLI | 6-8 ACs: a warning that suggests a split, exit 0 |
| AC-3 | `tests/test_engine.py::ScopeSizing::test_nine_draft_is_an_error`, `::test_nine_stale_is_an_error`, `::test_approved_eight_plus_ninth_is_stale`, `::test_approve_refuses_nine`, `tests/test_cli.py::…::test_validate_scope_size_exit_codes` | unit, CLI | 9+ ACs with the gate closed: the exact error, exit 1, approval refused |
| AC-4 | `tests/test_engine.py::ScopeSizing::test_nine_approved_only_warns`, `::test_this_repos_specs_have_no_scope_error`; S3 `sdlc validate --all` | unit, repo | approved specs only warn, and 0001-0010 stay green |
| AC-5 | `tests/test_cli.py::Docs::test_scope_sizing_guidance`; S3 `make check` and the `intent-first` eval | doc, eval | the advice ships, and the intent flow still works |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
