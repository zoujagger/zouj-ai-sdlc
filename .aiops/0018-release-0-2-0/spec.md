---
id: 0018
title: Release 0.2.0
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-25
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-25T09:33:15Z
approved-via: cli
approved-sha256: 8e16f93310b2af26c7e9b51c1cce6848e603691b14c90539c9aa08265eda54bb
---

# Spec: Release 0.2.0

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering requirements.
     Modeled on 0017's spec. The intent's two questions were accepted with its approval as proposed: the status
     line `**Status: 0.2.0.**` with a stability sentence, and the date the PR opens (corrected before the merge if
     it lands later). -->

## Summary
Main holds the AGPL-3.0 LICENSE (PR #36) and the README demo and Quick start (PRs #33-#35), but its tree still says
`0.2.0-beta.4` and `"license": "MIT"`. This change bumps the current version to **0.2.0** in `plugin.json`, the
README pins and the release tests, sets the license metadata to **AGPL-3.0-or-later** with a note that beta.4 and
earlier remain MIT, and adds a dated `[0.2.0]` CHANGELOG section without the beta banner. After the merge, the
merge commit is tagged `v0.2.0` and published as a GitHub release, not a pre-release. Nothing changes in behaviour
(intent: Desired outcome, Constraints).

## Requirements
- **R-1: the manifest.** `.claude-plugin/plugin.json` has `version` `0.2.0` and `license` `AGPL-3.0-or-later` (an
  SPDX id). `.claude-plugin/marketplace.json` names neither and isn't touched.
- **R-2: the CHANGELOG.**
  - **The new section:** `## [0.2.0] - 2026-11-25`, placed above `## [0.2.0-beta.4]`, with no beta banner. A lead
    line says 0.2.0 ends the beta series (0.2.0-alpha.1 … beta.4) and that the gates, the guards and what CI audits
    are unchanged since beta.4.
  - **`### Changed`:** the license: 0.2.0 and later are AGPL-3.0-or-later (`LICENSE`, `plugin.json`, PR #36);
    0.2.0-beta.4 and earlier remain MIT.
  - **`### Added`** (docs): the README demo GIF and the step-by-step Quick start with marketplace and clone installs
    (PRs #33-#35).
  - **The date:** the day the PR opens; if the merge lands on a later day, the heading is corrected in the PR before
    the merge, as a logged deviation.
  - **`[Unreleased]`** stays as an empty heading.
  - **The link references:** `[Unreleased]: …/compare/v0.2.0...HEAD` and
    `[0.2.0]: …/compare/v0.2.0-beta.4...v0.2.0`; the older links are unchanged.
- **R-3: the scaffold history** gains a `0.2.0` entry from `python3 scripts/scaffold-history.py`. No scaffold file
  changed since beta.4, so its hashes equal the beta.4 entry's; the released entries are unchanged and there is no
  `unreleased` key.
- **R-4: the README.**
  - **The status line:** `> **Status: 0.2.0.**` followed by a sentence saying the gates and file formats are
    stable within 0.2.x and the CHANGELOG names every change. It no longer says beta.
  - **The pins** name `v0.2.0`: both `marketplace add …@v0.2.0` commands, the clone's `checkout v0.2.0` and the
    settings snippet's `"ref"`.
  - **A `## License` section** at the end: AGPL-3.0-or-later from 0.2.0 (link to `LICENSE`); 0.2.0-beta.4 and
    earlier were released under the MIT License.
- **R-5: the tests that pin the current release.**
  - `test_version_matches_changelog` (`tests/test_shell_hooks.py`) and `test_changelog_has_the_release`
    (`tests/test_cli.py`) expect `0.2.0`.
  - `test_changelog_has_the_release`: the newest section names `AGPL-3.0-or-later`; the 0016 check moves to an
    explicit `## [0.2.0-beta.4]` slice; the README check becomes "no pre-release version (`0.2.0-alpha|beta|rc.N`)
    above `## Lifecycle`, and `@v0.2.0` appears twice"; `plugin.json`'s `license` is `AGPL-3.0-or-later`; the
    README has a `## License` section naming it and MIT.
  - `test_release_banner_is_beta` becomes `test_release_banner_is_not_prerelease`: the newest section's banner, if
    any, and the README status line name neither alpha nor beta.
  - No assertion that `[Unreleased]` is empty (it would hold only at the release commit).
- **R-6: nothing else changes.** No engine, hook, skill, template or schema behaviour; no license header in
  scaffold files; generated eval results keep their version strings.
- **R-7: the tag and the release, after the merge.** On the merge commit: an unsigned annotated tag `v0.2.0` with the
  message `zouj-ai-sdlc 0.2.0`, pushed, and a GitHub release named `0.2.0`, **not** `--prerelease` (marked latest),
  whose notes are the CHANGELOG section. Done by the agent only because zoujagger asked for it (2026-11-25).
- **Non-functional:** `make check`, `claude plugin validate .` and `scripts/scaffold-history.py --check` pass.

## Acceptance criteria
- **AC-1**: Given the release, when `plugin.json` is read, then `version` is `0.2.0` and `license` is
  `AGPL-3.0-or-later`, and the newest CHANGELOG release heading is `[0.2.0] - <date>` with the compare link from
  `v0.2.0-beta.4`.
- **AC-2**: Given the CHANGELOG, then `[Unreleased]` has no entries, and the 0.2.0 section has no beta banner and
  names the license change (AGPL-3.0-or-later from 0.2.0, MIT up to beta.4) and the README demo and Quick start.
- **AC-3**: Given the README, then the status line names `0.2.0` and neither alpha nor beta, every pin names
  `v0.2.0`, no pre-release version appears above `## Lifecycle`, and a `## License` section names AGPL-3.0-or-later
  and the earlier MIT releases.
- **AC-4**: Given the change, then `defaults/scaffold-history.json` has a `0.2.0` entry equal to the beta.4 entry
  and byte-identical released entries; only R-1 to R-5's files and `.aiops/0018-*` changed, and `make check`,
  `claude plugin validate .` and `scaffold-history.py --check` pass.

## Data model
None (no changes)

## API contracts
None (no changes)

## Security & data-leak flags
- ⚠️ **The pins point at a tag that doesn't exist until after the merge.** Until R-7 runs, an install from the README
  fails closed (the ref isn't found), as with every release. Mitigation: the tag follows the merge at once. (zoujagger)
- ⚠️ **License mix-up:** PR #36's own text said GPL-3.0 while its file is the AGPL. Mitigation: every place this
  change writes (manifest, README, CHANGELOG, release notes) says AGPL-3.0-or-later, and a test pins the manifest's
  SPDX id. (zoujagger)
- **The tag is unsigned**, as the betas were; the signed approvals and the CI audit are the guarantee. (zoujagger)
- No secret, approval, lock or audit path changes (R-6).

## Architecture
- **Where the version lives:** `plugin.json`. `cli.plugin_version()` reads it; from it come the scaffold's rendered
  ref (`v<version>`), the agent's `upgrade` pins and install-state's `plugin_version`, so the bump must land before
  the tag (intent: Problem).
- **The history lookup:** `lifecycle.history_key()` finds the running version in `defaults/scaffold-history.json`;
  with no new scaffold content, the 0.2.0 entry repeats the beta.4 hashes (R-3).
- **The license field** is metadata only: nothing in the engine reads it; `claude plugin validate .` checks the
  manifest.
- **Not taken:** tagging main as it is (the tree would say beta.4 and MIT).

## Rollout & rollback
- **Rollout:** one PR; after the human merges it, R-7 (tag, push, release). R-7 has no AC: it can only be true after
  the merge. Its check is `git rev-parse v0.2.0^{commit}` equal to the merge commit and `gh release view v0.2.0`
  showing a non-pre-release marked latest.
- **Upgrades:** repos on beta.4 move with `sdlc upgrade`; only the pinned ref changes.
- **Rollback:** revert the PR, and delete the tag and the release if they were published.

## Open questions
None. The intent's questions (the status line, the date) were accepted with its approval.
