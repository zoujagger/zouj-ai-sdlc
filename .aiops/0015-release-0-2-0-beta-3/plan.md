---
id: 0015
title: Release 0.2.0-beta.3
status: Approved
spec: ./spec.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T20:22:15Z
approved-via: cli
approved-sha256: 99492051ada24efd534d175f859d792e212768935fd9dce213c700b1fff4cad5
---

# Plan: Release 0.2.0-beta.3

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
A version bump, test-first, in two steps as for 0008 and 0010:

1. **S1:** the tests that pin the current release move to `0.2.0-beta.3` and fail (a commit with only them). Then
   everything those tests pin changes in one go, because one test covers all of it: the version source, the
   CHANGELOG, the scaffold history and the README pins.
2. **S2:** runs the checks at the release commit, and checks the diff's file list and the history entries.

Existing tests reused:
- **`tests/test_shell_hooks.py::…::test_version_matches_changelog`** (`:599`): the version, the newest CHANGELOG
  heading, and both compare links.
- **`tests/test_cli.py::Docs::test_changelog_has_the_release`** (`~:1226`):
  - the release section's content;
  - the README pins;
  - the history key. Between releases an `unreleased` key is allowed while `[Unreleased]` has entries, and at a
    release, with `[Unreleased]` empty, it is forbidden (`:1261-1262`), so it proves R-3 once the section moves.
- **`tests/test_cli.py::Docs::test_release_banner_is_beta`:** the newest section's banner.
- **`tests/test_rules.py::History`** and `scripts/scaffold-history.py --check`.
- **`tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl`**, unchanged (AC-5).

## Steps
- [x] **S1**: Bump the current release to 0.2.0-beta.3: the tests first, then the version, the CHANGELOG, the
  scaffold history and the README pins.
  - **Files (modify):**
    - `tests/test_shell_hooks.py`: `test_version_matches_changelog` expects `0.2.0-beta.3`.
    - `tests/test_cli.py`: `test_changelog_has_the_release`:
      - expects `0.2.0-beta.3`;
      - checks the beta.3 section for `.aiops/0011-scope-sizing/`, `.aiops/0012-dsl-part/`,
        `.aiops/0013-dsl-hardening/`, `.aiops/0014-spec-quality/` and `PR #29`;
      - the beta.2 section's checks (`.aiops/0009-stack-detection/`, `--stack auto`, `README`) move to an explicit
        `## [0.2.0-beta.2]` slice;
      - the beta.1 checks stay.
    - `.claude-plugin/plugin.json`: `version`.
    - `CHANGELOG.md`:
      - a new `## [0.2.0-beta.3] - 2026-11-20` section, with the beta banner and a lead line naming 0011-0014 and
        PR #29;
      - today's `[Unreleased]` entries moved under it unchanged, and `[Unreleased]` left empty;
      - the `[Unreleased]` and `[0.2.0-beta.3]` link references.
    - `defaults/scaffold-history.json`: regenerated with `python3 scripts/scaffold-history.py`, so `unreleased`
      becomes `0.2.0-beta.3`.
    - `README.md`: the status line, both `marketplace add …@v0.2.0-beta.3` lines and the settings `"ref"`.
  - **Test first:** both version tests fail on beta.2 (`'0.2.0-beta.2' != '0.2.0-beta.3'`).
  - Covers: AC-1, AC-2, AC-3, AC-4
- [ ] **S2**: Prove the release commit.
  - **Commands:**
    - `make check`;
    - `make validate` (`claude plugin validate .`);
    - `python3 scripts/scaffold-history.py --check`;
    - `bin/sdlc validate --all`.
  - **Diff check:** `git diff --name-only main...HEAD` lists only S1's files and `.aiops/0015-*`.
  - **History check:** a one-off script loads `defaults/scaffold-history.json` from `main` and from the tree, and
    checks that:
    - every released entry (0.1.0 … 0.2.0-beta.2) is equal;
    - the tree's `0.2.0-beta.3` entry equals main's `unreleased`.

    It's a one-off and not a test, because CI's shallow checkout has no `main`.
  - **CHANGELOG check:** a one-off comparison that the beta.3 section's `### Added` body is byte-equal to main's
    `[Unreleased]` body.
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-2, AC-3, AC-5

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The merge lands on a later day than the heading's date | medium | low | Correct the heading in the PR before the merge, logged as a deviation (spec R-2) |
| A current-version pin is missed | low | medium | `test_changelog_has_the_release` checks that every version string above `## Lifecycle` equals `plugin.json`, and S2's diff check |
| A released history entry changes | low | high | `scaffold-history.py` only renames `unreleased`; S2's one-off check compares every released entry with main |
| Anaconda's `ruff` on PATH reformats the repo if the hooks load | high if the hooks load | high | `git status` after each edit; restore anything outside the step |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_shell_hooks.py::…::test_version_matches_changelog`, `tests/test_cli.py::Docs::test_changelog_has_the_release` | unit | the version, the newest heading, the compare links |
| AC-2 | `tests/test_cli.py::Docs::test_changelog_has_the_release` (the beta.3 section), `::test_release_banner_is_beta`; S2 CHANGELOG check | doc, one-off | the entries moved unchanged; the banner and the lead line |
| AC-3 | `tests/test_cli.py::Docs::test_changelog_has_the_release` (no `unreleased` key), `tests/test_rules.py::History`; S2 history check and `--check` | unit, one-off | the beta.3 entry; released entries unchanged |
| AC-4 | `tests/test_cli.py::Docs::test_changelog_has_the_release` (the README pins) | doc | every pin says beta.3 |
| AC-5 | S2 diff check, `make check`, `make validate`; `tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl` | repo | only the planned files changed; nothing else moved |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
