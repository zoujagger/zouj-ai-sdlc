---
id: 0017
title: Release 0.2.0-beta.4
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-21
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-21T12:17:04Z
approved-via: cli
approved-sha256: cefa456788ecd123f9aab44d0c5431df6af8a833abbfc7f6675e158f3e35e5ae
---

# Spec: Release 0.2.0-beta.4

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements. Modeled on 0015's spec. The intent's one question (the release date) was accepted with its
     approval as proposed: the day the PR opens, corrected before the merge if it lands later. Re-drafted after the
     first spec approval: its AC-5 (the tag exists) could only hold after the merge, so it moved to Rollout. -->

## Summary
Intent 0016 (PR #31) is on main but in no release since `v0.2.0-beta.3`. This change bumps the current version to
**0.2.0-beta.4** in `plugin.json`, the README pins and the tests that pin the current release, and turns the
CHANGELOG's `[Unreleased]` entry into a dated `[0.2.0-beta.4]` section. After the merge, the merge commit is tagged
`v0.2.0-beta.4` and published as a GitHub pre-release. Nothing changes in behaviour (intent: Desired outcome,
Constraints).

## Requirements
- **R-1: the version.** `.claude-plugin/plugin.json` `version` is `0.2.0-beta.4`. `.claude-plugin/marketplace.json`
  names no version and isn't touched.
- **R-2: the CHANGELOG.**
  - **The new section:** what is under `## [Unreleased]` today (one `### Changed` entry, 0016) moves, unchanged,
    into a new `## [0.2.0-beta.4] - 2026-11-21` section placed above `## [0.2.0-beta.3]`.
  - **Its banner and lead:** the beta banner, worded as in beta.3, then one lead line naming
    `.aiops/0016-intent-skill-refinements/` and saying that the gates, the guards and what CI audits are unchanged.
  - **The date:** the day the PR opens; if the merge lands on a later day, the heading is corrected in the PR before
    the merge, as a logged deviation.
  - **`[Unreleased]`** stays as an empty heading.
  - **The link references:** `[Unreleased]: …/compare/v0.2.0-beta.4...HEAD` and
    `[0.2.0-beta.4]: …/compare/v0.2.0-beta.3...v0.2.0-beta.4`; the older links are unchanged.
- **R-3: the scaffold history** gains a `0.2.0-beta.4` entry: once `plugin.json` says beta.4,
  `python3 scripts/scaffold-history.py` adds the tree under that version, and `test_changelog_has_the_release`
  asserts `version in history`. Since 0016 changed no scaffold file, its hashes equal the beta.3 entry's. The
  released entries (0.1.0 … 0.2.0-beta.3) are unchanged, and there is no `unreleased` key. (This corrects the
  intent's Systems line, which said the file needs no change: the release test was read while writing this spec.)
- **R-4: the README pins** name `v0.2.0-beta.4`: the status line `beta (0.2.0-beta.4)`, both
  `marketplace add …@v0.2.0-beta.4` commands, and the settings snippet's `"ref"`. Earlier betas mentioned as history
  stay as they are.
- **R-5: the tests that pin the current release.**
  - `tests/test_shell_hooks.py::…::test_version_matches_changelog` and
    `tests/test_cli.py::Docs::test_changelog_has_the_release` expect `0.2.0-beta.4`.
  - `test_changelog_has_the_release` checks the newest section for `.aiops/0016-intent-skill-refinements/`; its
    beta.3 checks (0011-0014, `PR #29`) move to an explicit `## [0.2.0-beta.3]` slice, as 0015 did for beta.2. Its
    other checks are kept.
  - No assertion that `[Unreleased]` is empty (it would hold only at the release commit).
  - The 0011-0014 and 0016 guidance tests already search everything newer than their release, so they hold.
- **R-6: nothing else changes.** No engine, hook, skill, template or schema behaviour; generated eval results keep
  their version strings.
- **R-7: the tag and the pre-release, after the merge.** On the merge commit: an unsigned annotated tag
  `v0.2.0-beta.4` with the message `zouj-ai-sdlc 0.2.0-beta.4`, pushed, and a GitHub release named `0.2.0-beta.4`,
  `--prerelease`, whose notes are the CHANGELOG section (the beta.3 format). Done by the agent only because
  zoujagger asked for it (2026-11-21).
- **Non-functional:** `make check`, `claude plugin validate .` and `scripts/scaffold-history.py --check` pass.

## Acceptance criteria
- **AC-1**: Given the release, when `plugin.json` is read, then `version` is `0.2.0-beta.4`, and the newest CHANGELOG
  release heading is `[0.2.0-beta.4] - <date>` with the compare link from `v0.2.0-beta.3`.
- **AC-2**: Given the CHANGELOG, then `[Unreleased]` has no entries, and the beta.4 section holds, unchanged, the
  `### Changed` entry that `[Unreleased]` held on main at e86010b, after the beta banner and a lead line naming 0016.
- **AC-3**: Given the README, then the status line and every pin name `0.2.0-beta.4`, and no other version string
  appears above `## Lifecycle`.
- **AC-4**: Given the change, then `defaults/scaffold-history.json` has a `0.2.0-beta.4` entry equal to the beta.3
  entry and byte-identical released entries; only R-1 to R-5's files and `.aiops/0017-*` changed, and `make check`,
  `claude plugin validate .` and `scaffold-history.py --check` pass.

## Data model
None (no changes)

## API contracts
None (no changes)

## Security & data-leak flags
- ⚠️ **The pins point at a tag that doesn't exist until after the merge.** Until R-7 runs, an install from the README
  fails closed (the ref isn't found), as with every release. Mitigation: the tag follows the merge at once. (zoujagger)
- **The tag is unsigned**, as beta.1-beta.3 were; the signed approvals and the CI audit, not the tag, are the
  guarantee. (zoujagger)
- No secret, approval, lock or audit path changes (R-6).

## Architecture
- **Where the version lives:** `plugin.json`. `cli.plugin_version()` reads it; from it come the scaffold's rendered
  ref (`v<version>`), the agent's `upgrade` pins and install-state's `plugin_version`. This is why the bump must
  land before the tag (intent: Problem).
- **The history lookup:** `lifecycle.history_key()` finds the running version in `defaults/scaffold-history.json`;
  with no new scaffold content, the beta.4 entry repeats the beta.3 hashes (R-3).
- **Not taken:** tagging main as it is (the tree would say beta.3: the human chose this intent instead).

## Rollout & rollback
- **Rollout:** one PR; after the human merges it, R-7 (tag, push, pre-release). R-7 has no AC: it can only be
  true after the merge, while the review must find every AC met before it. Its check is `git rev-parse
  v0.2.0-beta.4^{commit}` equal to the merge commit and `gh release view v0.2.0-beta.4` showing a pre-release.
- **Upgrades:** repos on beta.3 move with `sdlc upgrade`; only the pinned ref changes.
- **Rollback:** revert the PR, and delete the tag and the release if they were published.

## Open questions
None. The intent's question (the date) was accepted with its approval.
