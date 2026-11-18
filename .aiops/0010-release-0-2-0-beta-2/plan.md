---
id: 0010
title: Release 0.2.0-beta.2
status: Approved
spec: ./spec.md
created: 2026-11-18
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-18T13:24:54Z
approved-via: cli
approved-sha256: 154a7e67ed387893e9bccca1095595a431466adf4094cec5e3f4451eb2a9147c
---

# Plan: Release 0.2.0-beta.2

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
A version bump, test-first, in two steps as for 0008.

1. **S1, the tests first.** The tests that pin the current release move to `0.2.0-beta.2` and fail. Then
   everything those tests pin changes in one go, because one test covers all of them:
   - the version source;
   - the CHANGELOG;
   - the scaffold history;
   - the README pins.
2. **S2** runs the full checks and the eval at the release commit, and checks the diff's file list.

Existing tests are reused:
- `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog` (`:599`): the version, the newest
  CHANGELOG heading, and both compare links.
- `tests/test_cli.py::Docs::test_changelog_has_the_release` (`:1095`): the release section's content, the empty
  `[Unreleased]`, the README pins, and the history key (with 0009's rule that `unreleased` is allowed only while
  `[Unreleased]` has entries).
- `tests/test_cli.py::Docs::test_release_banner_is_beta`: the newest section's banner.
- `tests/test_rules.py::History::test_current_scaffold_in_history` and `scripts/scaffold-history.py --check`.
- `tests/test_lifecycle.py::Detected::test_beta1_state_unchanged` (AC-7), unchanged.

## Steps
- [ ] **S1**: Bump the current release to 0.2.0-beta.2: tests first, then the version source, the CHANGELOG, the
  scaffold history and the README and roadmap.
  - **Files (modify):**
    - `tests/test_shell_hooks.py`: `test_version_matches_changelog` expects `0.2.0-beta.2`.
    - `tests/test_cli.py`:
      - `test_changelog_has_the_release` expects `0.2.0-beta.2`;
      - it checks the beta.2 section for `.aiops/0009-stack-detection/`, `--stack auto` and `README`;
      - the beta.1 section's existing checks move to an explicit `## [0.2.0-beta.1]` lookup;
      - a new assertion: `[Unreleased]` has no `### ` heading.
    - `.claude-plugin/plugin.json`: `version`.
    - `CHANGELOG.md`: the new `## [0.2.0-beta.2] - 2026-11-18` section, with the beta banner and a lead line naming
      0009 and PR #22, and today's `[Unreleased]` entries moved under it unchanged. `[Unreleased]` is left empty, and
      the two link references are updated.
    - `defaults/scaffold-history.json`: regenerated with `python3 scripts/scaffold-history.py`, so `unreleased`
      becomes `0.2.0-beta.2`.
    - `README.md`: the status line, both `marketplace add …@v0.2.0-beta.2` lines and the settings `"ref"`.
    - `docs/roadmap.md`: the "Adoption, part 2" entries say they shipped in 0.2.0-beta.2.
  - **Test first:** `test_version_matches_changelog` and `test_changelog_has_the_release` fail on beta.1
    (`'0.2.0-beta.1' != '0.2.0-beta.2'`).
  - Covers: AC-1, AC-2, AC-3, AC-4
- [ ] **S2**: Prove the release commit.
  - **Commands:**
    - `make check`;
    - `claude plugin validate .`;
    - `python3 scripts/scaffold-history.py --check`;
    - the `profile-by-setup-command` eval with the plugin (3 runs per arm, as in 0008 S3).
  - **Diff check:** `git diff --name-only origin/main` lists only R-1 to R-5's files and `.aiops/0010-*`.
  - **History check:** a one-off script loads `defaults/scaffold-history.json` from `origin/main` and from the tree,
    and checks that:
    - every released entry (0.1.0 … 0.2.0-beta.1) is equal;
    - the tree's `0.2.0-beta.2` entry equals main's `unreleased` entry.

    It's a one-off and not a test, because CI's shallow checkout has no `origin/main`.
  - **Files:** none (`evals/results/<run>/` is generated).
  - **Test first:** none; this step is the verification itself. Its results are recorded in the Deviation log and
    quoted in review.md.
  - Covers: AC-5, AC-6, AC-7

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `scaffold-history.py` changes released entries (e.g. a template read differently) | low | upgrades misjudge files | S2's history check against `origin/main` |
| The merge happens on a later day than the CHANGELOG heading | medium | wrong release date | correct the heading in the PR before the merge (a logged deviation), as the spec says |
| A historical beta.1 mention is bumped by mistake | low | docs misstate history | only the four README pins, `plugin.json`, the CHANGELOG and the roadmap entries change; AC-5's file list |
| `test_changelog_has_the_release` loses its beta.1 coverage | low | weaker release test | the beta.1 checks are kept under an explicit `[0.2.0-beta.1]` lookup |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog` | unit | version, newest heading, compare links |
| AC-2 | `tests/test_cli.py::Docs::test_changelog_has_the_release`, `::test_release_banner_is_beta` | docs | beta.2 section content, empty `[Unreleased]`, beta banner |
| AC-3 | `tests/test_rules.py::History::test_current_scaffold_in_history`; `scripts/scaffold-history.py --check`; S2's history check | unit, check | beta.2 key, no `unreleased`, released entries untouched |
| AC-4 | `tests/test_cli.py::Docs::test_changelog_has_the_release` | docs | README pins and status line name beta.2, no other version above Lifecycle |
| AC-5 | `git diff --name-only origin/main` (S2) | check | only the named files changed |
| AC-6 | `make check`, `claude plugin validate .`, eval `profile-by-setup-command` (S2) | gate | the release commit passes |
| AC-7 | `tests/test_lifecycle.py::Detected::test_beta1_state_unchanged` | integration | beta.1 preset-wired Makefiles keep their recipes on upgrade |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
