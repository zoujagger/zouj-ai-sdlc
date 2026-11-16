---
id: 0008
title: Release 0.2.0-beta.1
status: Approved
spec: ./spec.md
created: 2026-11-16
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-16T16:19:07Z
approved-via: cli
approved-sha256: 084edcf92656854d96935863e7fd004147139c36392d2290acc4ae8a9d0992d0
---

# Plan: Release 0.2.0-beta.1

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
A version rename, test-first. First the tests that pin the version move to `0.2.0-beta.1`, and new assertions say
that no shipped file names alpha.4 and no banner says alpha; they fail. Then the version source (`plugin.json`),
the CHANGELOG and the scaffold history change (S1), then the docs (S2). The last step runs the full checks and
the eval at the release commit (S3). The existing tests are reused:
- `tests/test_shell_hooks.py` `test_version_matches_changelog` (the version, the newest CHANGELOG heading and its
  compare link)
- `tests/test_cli.py` `Docs::test_changelog_has_the_release` (the README pins match `plugin.json`)
- `tests/test_rules.py` `History::test_current_scaffold_in_history`

## Steps
- [ ] **S1**: Rename the release to 0.2.0-beta.1 in the version source, the CHANGELOG and the scaffold history.
  - Files: `.claude-plugin/plugin.json`, `CHANGELOG.md` (the heading with the merge date, the beta banner, both
    link references), `defaults/scaffold-history.json` (the key renamed, same hashes) (modify)
  - Test first: `tests/test_shell_hooks.py::test_version_matches_changelog` and
    `tests/test_cli.py::Docs::test_changelog_has_the_release` expect `0.2.0-beta.1`.
    `tests/test_rules.py::History::test_current_scaffold_in_history` also asserts a `0.2.0-beta.1` entry and no
    `0.2.0-alpha.4` key. A new `tests/test_cli.py::Docs::test_release_banner_is_beta` checks that the newest
    CHANGELOG section's banner doesn't say "Alpha". These fail on alpha.4.
  - Covers: AC-1, AC-3, AC-4
- [ ] **S2**: Rename every remaining alpha.4 mention in the shipped docs and the README's alpha status line.
  - Files: `README.md` (status line, current release, the three pins, the install-state note),
    `TROUBLESHOOTING.md`, `docs/adoption.md`, `docs/roadmap.md`, the `lib/sdlc_engine/lifecycle.py` docstring
    (modify)
  - Test first: a new `tests/test_cli.py::Docs::test_no_shipped_file_names_alpha_4` walks the git-tracked files
    outside `.aiops/` and `evals/results/` and finds no `alpha.4`. `test_release_banner_is_beta` also checks that
    the README's status line doesn't say alpha. Both fail before the edit.
  - Covers: AC-2, AC-4
- [ ] **S3**: Prove the release commit: `make check`, `claude plugin validate .`, and the
  `profile-by-setup-command` eval with the plugin (3 runs per arm, as in 0007 S19). Then check that
  `git diff --name-only origin/main` lists only R-1 to R-5's files and `.aiops/0008-*`.
  - Files: none (`evals/results/<run>/` is generated)
  - Test first: none; this step is the verification itself. Its results are recorded in the Deviation log and
    quoted in review.md.
  - Covers: AC-5, AC-6

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `scripts/scaffold-history.py` regenerates more than the key rename | low | the history changes hashes | Rename the key by hand, and compare the old and new entries' hashes in the test |
| A version mention outside the listed files is missed | low | a stale alpha.4 ships | `test_no_shipped_file_names_alpha_4` searches every tracked file |
| The eval is flaky or costs too much | medium | AC-6 can't be shown | Run the single case only; if it fails, report the run as it is and let the human decide |
| The README pin points at a tag that doesn't exist yet | certain until tagged | an install before the tag fails | The human tags right after the merge (spec Rollout) |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_shell_hooks.py::test_version_matches_changelog`, `tests/test_cli.py::Docs::test_changelog_has_the_release` | unit | `plugin.json` is beta.1; the newest CHANGELOG heading and its compare link from alpha.3 |
| AC-2 | `tests/test_cli.py::Docs::test_no_shipped_file_names_alpha_4` | unit | no tracked file outside `.aiops/` and `evals/results/` names alpha.4 |
| AC-3 | `tests/test_rules.py::History::test_current_scaffold_in_history` | unit | a beta.1 history entry, no alpha.4 key, the current scaffold matches |
| AC-4 | `tests/test_cli.py::Docs::test_changelog_has_the_release`, `tests/test_cli.py::Docs::test_release_banner_is_beta` | unit | every README pin is the version; neither the README status line nor the CHANGELOG banner says alpha |
| AC-5 | S3: `git diff --name-only origin/main` | manual | only the intended files change |
| AC-6 | S3: `make check`, `claude plugin validate .`, the `profile-by-setup-command` eval | integration / e2e | the release commit passes; the eval run is quoted in review.md |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
