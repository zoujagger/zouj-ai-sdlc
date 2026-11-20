---
id: 0015
title: Release 0.2.0-beta.3
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T20:20:24Z
approved-via: cli
approved-sha256: d77b4a076ce9c75da82d4860a58113120bae424176eae3b94532451e83beda11
---

# Spec: Release 0.2.0-beta.3

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements. Modeled on 0010's spec. The intent's questions were answered: the merge date, and the docs audit
     in the lead line only. -->

## Summary
These changes are on main but not in any release since `v0.2.0-beta.2`:
- scope sizing (intent 0011);
- the opt-in `dsl` part (0012) and its hardening (0013);
- sharper specs (0014);
- the docs audit (PR #29).

This change bumps the current version to **0.2.0-beta.3**:
- in `plugin.json`;
- in the README pins;
- in the tests that pin the current release.

It also does these:
- turns the CHANGELOG's `[Unreleased]` entries into a dated `[0.2.0-beta.3]` section;
- renames scaffold-history's `unreleased` entry to `0.2.0-beta.3`.

After the merge the human tags `v0.2.0-beta.3`. Nothing changes in behaviour (intent: Desired outcome,
Constraints).

## Requirements
- **R-1: the version.** `.claude-plugin/plugin.json` `version` is `0.2.0-beta.3`. `.claude-plugin/marketplace.json`
  names no version and isn't touched.
- **R-2: the CHANGELOG.**
  - **The new section:** what is under `## [Unreleased]` today (one `### Added` with three entries: 0014, 0012 with
    0013, 0011) moves, unchanged, into a new `## [0.2.0-beta.3] - 2026-11-20` section placed above
    `## [0.2.0-beta.2]`.
  - **Its banner and lead:** the section opens with the beta banner, worded as in beta.2, then one lead line naming
    `.aiops/0011-scope-sizing/`, `.aiops/0012-dsl-part/` with `.aiops/0013-dsl-hardening/`,
    `.aiops/0014-spec-quality/`, and the docs audit (PR #29).
  - **The date:** the merge date, written as the day the PR opens. If the merge happens on a later day, the heading
    is corrected in the PR before the merge, as a logged deviation.
  - **`[Unreleased]`** stays as an empty heading.
  - **The link references** become:
    - `[Unreleased]: …/compare/v0.2.0-beta.3...HEAD`
    - `[0.2.0-beta.3]: …/compare/v0.2.0-beta.2...v0.2.0-beta.3`
    - The older links are unchanged.
- **R-3: the scaffold history.** In `defaults/scaffold-history.json`, the `unreleased` entry becomes
  `0.2.0-beta.3`, with the same hashes. `python3 scripts/scaffold-history.py` does this once `plugin.json` says
  beta.3. The released entries (0.1.0 … 0.2.0-beta.2) are unchanged.
- **R-4: the README pins** name `v0.2.0-beta.3`:
  - the status line: `beta (0.2.0-beta.3)`;
  - both `marketplace add …@v0.2.0-beta.3` commands;
  - the settings snippet's `"ref"`.

  Mentions of earlier betas as history stay as they are (`docs/roadmap.md`, `docs/adoption.md`, `docs/lifecycle.md`,
  test comments).
- **R-5: the tests that pin the current release.**
  - `tests/test_shell_hooks.py::…::test_version_matches_changelog` and
    `tests/test_cli.py::Docs::test_changelog_has_the_release` expect `0.2.0-beta.3`.
  - `test_changelog_has_the_release` checks the beta.3 section for:
    - `.aiops/0011-scope-sizing/`, `.aiops/0012-dsl-part/`, `.aiops/0013-dsl-hardening/` and
      `.aiops/0014-spec-quality/`;
    - `PR #29`.

    Its beta.2 checks (`.aiops/0009-stack-detection/`, `--stack auto`, the README funnel) move to an explicit
    `## [0.2.0-beta.2]` slice. Its other checks are kept: `[Unreleased]` holds no "Planned as", the compare link,
    and every README pin matches `plugin.json`.
  - It adds no assertion that `[Unreleased]` is empty, which would hold only at the release commit (0011 S2
    deviation).
  - `tests/test_rules.py::History` keeps asserting the earlier entries, and passes with the new beta.3 entry.
- **R-6: nothing else changes.**
  - No engine, hook, skill, template or schema behaviour changes.
  - Generated eval results (`evals/results/*`) keep their version strings.
- **Non-functional:** `make check`, `claude plugin validate .` and `scripts/scaffold-history.py --check` pass.

## Acceptance criteria
- **AC-1**: Given the release, when `plugin.json` is read, then `version` is `0.2.0-beta.3`, and the newest
  CHANGELOG release heading is `[0.2.0-beta.3] - <date>`, with the compare link from `v0.2.0-beta.2`
  (`test_version_matches_changelog`, `test_changelog_has_the_release`).
- **AC-2**: Given the CHANGELOG, then `[Unreleased]` has no entries, and the beta.3 section holds, unchanged, the
  `### Added` entries that `[Unreleased]` held on main at 8d61c72, after the beta banner and a lead line naming
  0011-0014 and PR #29.
- **AC-3**: Given `defaults/scaffold-history.json`, then:
  - it has a `0.2.0-beta.3` entry with the hashes the `unreleased` entry had;
  - it has no `unreleased` key;
  - the released entries are byte-identical to main's;
  - `scripts/scaffold-history.py --check` reports it up to date.
- **AC-4**: Given the README, then the status line and every pin name `0.2.0-beta.3`, and no other version string
  appears above `## Lifecycle` (`test_changelog_has_the_release`).
- **AC-5**: Given the change, when `git diff --name-only main...HEAD` is read, then only R-1 to R-5's files and
  `.aiops/0015-*` changed, and `make check` and `claude plugin validate .` pass. A Makefile wired by detection still
  keeps its recipes through `upgrade` (`Detected::test_wired_makefile_keeps_recipes_with_validate_dsl`, unchanged).

## Data model
None (no changes)

## API contracts
None (no changes)

## Security & data-leak flags
- ⚠️ **The pins point at a tag that doesn't exist yet.** The README pins and the scaffold's rendered
  `ZOUJ_SDLC_REF` point at `v0.2.0-beta.3`, which won't exist until the human creates it, as with every release so
  far. Until then an install from the README fails closed (the ref isn't found). Mitigation: the human tags right
  after the merge (Rollout). (zoujagger)
- No secret, approval, lock or audit path changes (R-6).

## Architecture
- **Where the version lives:** `plugin.json`. `cli.plugin_version()` reads it, and from it come the scaffold's
  rendered ref (`v<version>`), the agent's `upgrade` pins, and install-state's `plugin_version`.
- **The history lookup:** `lifecycle.history_key()` finds the running version in `defaults/scaffold-history.json`,
  which R-3 keeps true.
- **Not taken:**
  - keeping the `unreleased` history key until the tag exists (the release test requires the version's entry);
  - a `### Changed` entry for the docs audit (the human chose the lead line).

## Rollout & rollback
- **Rollout:**
  1. One PR.
  2. After it merges, the human tags `v0.2.0-beta.3` on the merge commit and pushes the tag, which drafts the
     GitHub release.
  3. The human then publishes the release.
- **Upgrades:** repos on beta.2 move with `sdlc upgrade`. Untouched templates are replaced, including the Makefile,
  which gains the dormant `validate-dsl` target and keeps its recipes.
- **Rollback:** revert the PR, and delete the tag if one was pushed.

## Open questions
None. The intent's questions were answered (the merge date; the docs audit in the lead line).
