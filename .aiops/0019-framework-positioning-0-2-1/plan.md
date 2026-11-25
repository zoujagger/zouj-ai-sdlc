---
id: 0019
title: Framework positioning and release 0.2.1
status: Approved
spec: ./spec.md
created: 2026-11-25
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-25T11:54:05Z
approved-via: cli
approved-sha256: b30a6395024ef48c07375cd035d599d0e7be29ba893578432b765f70ed3f6b96
---

# Plan: Framework positioning and release 0.2.1

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Two TDD steps and one verification step; the tag, the release and the repository description (spec R-9) follow the
merge and are not plan steps.

1. **S1, positioning:** a new `Docs` test pins the wording (red), then the manifests, `CLAUDE.md`, the practices
   section and the README (the intro rewritten before this intent, plus the link) turn it green.
2. **S2, release 0.2.1:** the release tests move to `0.2.1` (red), then the version, CHANGELOG, README pins and
   scaffold history turn them green.
3. **S3:** verification.

Code reused: `test_changelog_has_the_release` (`tests/test_cli.py:1263`), `test_version_matches_changelog`
(`tests/test_shell_hooks.py:601`), `scripts/scaffold-history.py`, 0018's release pattern.

## Steps
- [x] **S1**: State the framework positioning.
  - **Files:**
    - `tests/test_cli.py` (modify): new `Docs.test_framework_positioning`: both manifest descriptions contain
      `AI-native software engineering framework` and none of `orchestration`, `guarantee`, `sandbox`; `CLAUDE.md`
      contains `an AI-native software engineering framework implemented as a Claude Code plugin`; `docs/sdlc.md` has
      `## Engineering practices` naming the six practices and `enforcement.md`; the README contains
      `docs/sdlc.md#engineering-practices` (AC-1, AC-2).
    - `.claude-plugin/plugin.json` (modify): `description` per R-1.
    - `.claude-plugin/marketplace.json` (modify): the plugin entry's `description` per R-2.
    - `CLAUDE.md` (modify): the opening sentence per R-3.
    - `docs/sdlc.md` (modify): `## Engineering practices` per R-4.
    - `README.md` (modify): the intro and list already in the working tree, plus the practices link (R-5).
  - **Test first:** the new test fails on the manifest description.
  - Covers: AC-1, AC-2
- [x] **S2**: Release 0.2.1.
  - **Files:**
    - `tests/test_shell_hooks.py` (modify): `test_version_matches_changelog` expects `0.2.1`.
    - `tests/test_cli.py` (modify): `test_changelog_has_the_release` expects `0.2.1`; the newest section names
      `AI-native software engineering framework`, `Copyright` and `CLA`; the 0.2.0 checks move to a `## [0.2.0]`
      slice (AC-3, AC-4, AC-5).
    - `.claude-plugin/plugin.json` (modify): `version` `0.2.1`.
    - `CHANGELOG.md` (modify): `## [0.2.1] - 2026-11-25` per R-6, `[Unreleased]` empty, the two links.
    - `README.md` (modify): status line and the four pins.
    - `defaults/scaffold-history.json` (regenerate): a `0.2.1` entry equal to `0.2.0`'s.
  - **Test first:** both release tests fail on the version (`0.2.0` != `0.2.1`).
  - Covers: AC-3, AC-4, AC-5
- [x] **S3**: Prove the change.
  - **Commands:** `make check`; `make validate`; `python3 scripts/scaffold-history.py --check`; a JSON comparison
    (the `0.2.1` entry equals `0.2.0`'s, released entries equal main's); `git diff --name-only main...HEAD` (only
    S1-S2's files and `.aiops/0019-*`); a README link check (every relative link and anchor resolves).
  - **Files:** none. Results go in the Deviation log and review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-5

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `claude plugin validate` rejects the longer description | low | low | `make validate` in S3 |
| The PR merges on a later day than the CHANGELOG date | medium | low | correct the heading before the merge, logged |
| README pins name a tag that doesn't exist yet | certain until R-9 | low: fails closed | tag right after the merge |
| Anaconda's `ruff` reformats the repo if the hooks load | high if loaded | high | `git status` after each edit |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_cli.py::Docs::test_framework_positioning` | unit | manifest and marketplace descriptions, banned words, `CLAUDE.md` sentence |
| AC-2 | `tests/test_cli.py::Docs::test_framework_positioning` | unit | the practices section, its six practices and limit link, the README link |
| AC-3 | `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog`; `tests/test_cli.py::Docs::test_changelog_has_the_release` | unit | version, CHANGELOG section, compare link |
| AC-4 | `test_changelog_has_the_release` (README part); `test_release_banner_is_not_prerelease` | unit | status line and pins |
| AC-5 | `test_changelog_has_the_release` (`version in history`); S3 commands | unit, repo | history entry, scope, checks green |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-25 | S3 | Results: `make check` OK (577 tests, 3 skipped) on 3490821; `make validate` passed with the one existing warning (root `CLAUDE.md`); `scaffold-history.py --check` up to date; the `0.2.1` entry equals `0.2.0`'s and every entry on `origin/main` is unchanged, no `unreleased` key; every README relative link and anchor resolves; `git diff --name-only origin/main...HEAD` lists only S1-S2's files and `.aiops/0019-*`. Red commits: 7f3f31a (positioning test fails on the manifest description), f439e8a (both fail `'0.2.0' != '0.2.1'`). The comparison base is `origin/main`: the local `main` ref is behind it | The verification itself; no deviation from the plan | 3490821 |
