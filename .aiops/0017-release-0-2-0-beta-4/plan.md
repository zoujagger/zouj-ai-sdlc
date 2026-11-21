---
id: 0017
title: Release 0.2.0-beta.4
status: Approved
spec: ./spec.md
created: 2026-11-21
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-21T12:19:26Z
approved-via: cli
approved-sha256: 3d0eaf4797090c8d766f5e0752f9a517ba09d83ac92552073bf3a9653daed8ea
---

# Plan: Release 0.2.0-beta.4

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Modeled on 0015. One TDD step and one verification step; the tag and the pre-release (spec R-7) follow the merge
and are not plan steps.

1. **S1:** the tests that pin the current release move to `0.2.0-beta.4` and fail (a commit with only them). Then
   the bump turns them green: `plugin.json`, the CHANGELOG section, the README pins, and the regenerated scaffold
   history.
2. **S2:** verification.

Code reused: `scripts/scaffold-history.py` (adds the `0.2.0-beta.4` entry once `plugin.json` says it); the beta.3
section of `CHANGELOG.md` for the banner wording; `test_changelog_has_the_release` (`tests/test_cli.py:1260`) and
`ShellHooks::test_version_matches_changelog` (`tests/test_shell_hooks.py:599`). The 0011-0014 and 0016 guidance
tests already search everything newer than their release, so they hold after the release.

## Steps
- [ ] **S1**: Bump the release to 0.2.0-beta.4.
  - **Files:**
    - `tests/test_shell_hooks.py` (modify): `test_version_matches_changelog` expects `0.2.0-beta.4` (AC-1).
    - `tests/test_cli.py` (modify): `test_changelog_has_the_release` expects `0.2.0-beta.4`; the newest section
      must name `.aiops/0016-intent-skill-refinements/`; the 0011-0014 and `PR #29` checks move to an explicit
      `## [0.2.0-beta.3]` slice (AC-1, AC-2, AC-3, AC-4).
    - `.claude-plugin/plugin.json` (modify): `version` `0.2.0-beta.4` (R-1).
    - `CHANGELOG.md` (modify): the `[Unreleased]` entry moves unchanged into `## [0.2.0-beta.4] - 2026-11-21`, with
      the beta banner and a lead line naming 0016; `[Unreleased]` empty; the two compare links (R-2).
    - `README.md` (modify): the status line, both marketplace commands and the settings `"ref"` (R-4).
    - `defaults/scaffold-history.json` (regenerate with `python3 scripts/scaffold-history.py`): a `0.2.0-beta.4`
      entry equal to beta.3's (R-3).
  - **Test first:** both tests fail on the version (`0.2.0-beta.3` != `0.2.0-beta.4`).
  - Covers: AC-1, AC-2, AC-3, AC-4
- [ ] **S2**: Prove the change.
  - **Commands:**
    - `make check`;
    - `make validate`;
    - `python3 scripts/scaffold-history.py --check`;
    - a JSON comparison: the `0.2.0-beta.4` history entry equals `0.2.0-beta.3`'s, and the released entries equal
      main's;
    - `git diff main...HEAD -- CHANGELOG.md`: the 0016 entry moved unchanged;
    - `git diff --name-only main...HEAD`: only S1's files and `.aiops/0017-*`.
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-2, AC-4

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The PR merges on a later day than the CHANGELOG date | medium | low | Correct the heading in the PR before the merge, as a logged deviation (spec R-2) |
| The README pins name a tag that doesn't exist yet | certain until R-7 | low: an install fails closed | Tag and publish right after the merge (spec Rollout) |
| A guidance test still reads only `[Unreleased]` and loses its entry | low | low: a red test | They search everything newer than their release (0015 S1, 0016); `make check` in S2 |
| Anaconda's `ruff` on PATH reformats the repo if the hooks load | high if the hooks load | high | `git status` after each edit; restore anything outside the step |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog`; `tests/test_cli.py::Docs::test_changelog_has_the_release` | unit | `plugin.json` and the newest CHANGELOG release agree on beta.4, with the compare link |
| AC-2 | `test_changelog_has_the_release` (0016 in the newest section; beta.3 slice keeps 0011-0014); S2 CHANGELOG diff | unit, repo | the entry moved unchanged; `[Unreleased]` empty at the release commit |
| AC-3 | `test_changelog_has_the_release` (README part) | unit | every README pin names beta.4 |
| AC-4 | `test_changelog_has_the_release` (`version in history`); S2 `scaffold-history.py --check`, JSON comparison, file list, `make check`, `make validate` | unit, repo | the history entry, the scope, everything green |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
