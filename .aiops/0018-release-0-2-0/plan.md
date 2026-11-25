---
id: 0018
title: Release 0.2.0
status: Approved
spec: ./spec.md
created: 2026-11-25
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-25T09:33:59Z
approved-via: cli
approved-sha256: fe883982ba9b6bb53b6a60d688aab5bb012c9ba3f706a09c5d36f2b0a55f9bdc
---

# Plan: Release 0.2.0

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Modeled on 0017. One TDD step and one verification step; the tag and the release (spec R-7) follow the merge and
are not plan steps.

1. **S1:** the tests that pin the current release move to `0.2.0` and the AGPL license and fail (a commit with only
   them). Then the bump turns them green: `plugin.json`, the CHANGELOG section, the README (status line, pins,
   License section), and the regenerated scaffold history.
2. **S2:** verification.

Code reused: `scripts/scaffold-history.py` (adds the `0.2.0` entry once `plugin.json` says it);
`test_changelog_has_the_release` (`tests/test_cli.py:1260`), `test_release_banner_is_beta` (`tests/test_cli.py:1237`)
and `test_version_matches_changelog` (`tests/test_shell_hooks.py:601`). The 0011-0016 guidance tests already
search everything newer than their release, so they hold after the release.

## Steps
- [ ] **S1**: Bump the release to 0.2.0 under AGPL-3.0-or-later.
  - **Files:**
    - `tests/test_shell_hooks.py` (modify): `test_version_matches_changelog` expects `0.2.0` (AC-1).
    - `tests/test_cli.py` (modify): `test_changelog_has_the_release` expects `0.2.0`, `plugin.json` `license`
      `AGPL-3.0-or-later`, `0.2.0` a key of `defaults/scaffold-history.json`, the newest section naming `AGPL-3.0-or-later`, `MIT` and `Quick start`; the 0016 check
      moves to an explicit `## [0.2.0-beta.4]` slice; the README check: no `0.2.0-(alpha|beta|rc).N` above
      `## Lifecycle`, `@v0.2.0` twice, `checkout v0.2.0`, a `## License` section naming `AGPL-3.0-or-later` and
      `MIT`. `test_release_banner_is_beta` becomes `test_release_banner_is_not_prerelease`: the newest section's
      `>` banner, if any, and the README status line name neither alpha nor beta (AC-1, AC-2, AC-3, AC-4).
    - `.claude-plugin/plugin.json` (modify): `version` `0.2.0`, `license` `AGPL-3.0-or-later` (R-1).
    - `CHANGELOG.md` (modify): `## [0.2.0] - 2026-11-25` with the lead line, `### Changed` (license) and `### Added`
      (README demo and Quick start, PRs #33-#35); `[Unreleased]` empty; the two compare links (R-2).
    - `README.md` (modify): the status line, both marketplace commands, the clone checkout, the settings `"ref"`, and
      a `## License` section at the end (R-4).
    - `defaults/scaffold-history.json` (regenerate with `python3 scripts/scaffold-history.py`): a `0.2.0` entry
      equal to beta.4's (R-3).
  - **Test first:** both version tests fail (`0.2.0-beta.4` != `0.2.0`), and the license and README checks fail.
  - Covers: AC-1, AC-2, AC-3, AC-4
- [ ] **S2**: Prove the change.
  - **Commands:**
    - `make check`;
    - `make validate`;
    - `python3 scripts/scaffold-history.py --check`;
    - a JSON comparison: the `0.2.0` history entry equals `0.2.0-beta.4`'s, and the released entries equal main's;
    - `git diff --name-only main...HEAD`: only S1's files and `.aiops/0018-*`.
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-2, AC-4

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The PR merges on a later day than the CHANGELOG date | medium | low | Correct the heading in the PR before the merge, as a logged deviation (spec R-2) |
| The README pins name a tag that doesn't exist yet | certain until R-7 | low: an install fails closed | Tag and publish right after the merge (spec Rollout) |
| `claude plugin validate` rejects the SPDX id | low | low: a red check | S2 runs `make validate`; `AGPL-3.0-or-later` is a valid SPDX id |
| A README Quick start test reads a pin that moved | low | low: a red test | `make check` in S2 |
| Anaconda's `ruff` on PATH reformats the repo if the hooks load | high if the hooks load | high | `git status` after each edit; restore anything outside the step |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog`; `tests/test_cli.py::Docs::test_changelog_has_the_release` | unit | `plugin.json` (version, license) and the newest CHANGELOG release agree on 0.2.0, with the compare link |
| AC-2 | `test_changelog_has_the_release` (license and Quick start in the newest section); `test_release_banner_is_not_prerelease` | unit | the section's content, no beta banner |
| AC-3 | `test_changelog_has_the_release` (README part); `test_release_banner_is_not_prerelease` (status line) | unit | the status line, every pin, the License section |
| AC-4 | `test_changelog_has_the_release` (`version in history`); S2 `scaffold-history.py --check`, JSON comparison, file list, `make check`, `make validate` | unit, repo | the history entry, the scope, everything green |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
