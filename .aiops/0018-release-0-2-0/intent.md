---
id: 0018
title: Release 0.2.0
status: Approved
owner: zoujagger
initiator: zoujagger
source: request to merge PR #36 (LICENSE → AGPL-3.0) and release 0.2.0, 2026-11-25
created: 2026-11-25
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-25T09:32:15Z
approved-via: cli
approved-sha256: ed77567634f13be20b466ff85904e6857f7c31f2a76ea97dfe01e77f6d8ddad1
---

# Intent: Release 0.2.0

<!-- State 1 BRAINSTORMING. Modeled on intent 0017 (the beta.4 release). The scope check passed: one workflow, a
     version bump plus the license metadata. zoujagger chose AGPL-3.0-or-later (2026-11-25) after PR #36's text
     said GPL-3.0 while its LICENSE file is the AGPL. Unknowns go in Open questions, never invented. approved-*
     fields are stamped by the human approval; agents never write them. -->

## Problem
Since `v0.2.0-beta.4`, main gained the README demo GIF and Quick start (PRs #33-#35) and a new LICENSE (PR #36,
merged as fea5b57): from 0.2.0 the plugin is distributed under the **GNU Affero GPL v3.0 or later**; releases up to
0.2.0-beta.4 stay MIT. Tagging main as it is would ship a `v0.2.0` whose tree contradicts itself:

- `plugin.json` names `0.2.0-beta.4` (so `sdlc init` would pin a scaffolded repo's CI to beta.4) and declares
  `"license": "MIT"` while the LICENSE file is the AGPL;
- the CHANGELOG has nothing under `[Unreleased]` for the license change or the README work;
- the README's status line still calls it a beta, and its marketplace, clone and settings pins name beta.4.

## Desired outcome
- **The tree describes 0.2.0** everywhere a current version appears: `plugin.json`, the README pins (the status
  line, the marketplace commands, the clone checkout and the settings snippet) and the tests that pin the release.
- **The license metadata matches the LICENSE file:** `plugin.json` says `AGPL-3.0-or-later`, and the README and
  CHANGELOG say that 0.2.0 and later are AGPL-3.0-or-later while 0.2.0-beta.4 and earlier remain MIT.
- **The CHANGELOG** has a dated `[0.2.0]` section naming the license change and the README/demo work, without the
  beta banner; `[Unreleased]` is left empty and the compare links are updated.
- **Checks pass** at the release commit: `make check`, `claude plugin validate .`, and `scaffold-history.py --check`.
- **After the merge**, the merge commit is tagged `v0.2.0` and published as a GitHub release (not a pre-release),
  at the human's request, and the README's pins resolve.

## Users & systems affected
- **Users:** people installing from a tag or the marketplace, who now receive AGPL-licensed code; repos scaffolded
  by `sdlc init`/`setup`, whose workflows pin the plugin at `v<version>` and whose `sdlc upgrade` moves them from
  beta.4.
- **Systems:** `.claude-plugin/plugin.json`, `CHANGELOG.md`, `README.md`, `defaults/scaffold-history.json`, and the
  release tests (`tests/test_cli.py::Docs::test_changelog_has_the_release`,
  `tests/test_shell_hooks.py::…::test_version_matches_changelog`).

## Constraints
- **A version bump and license metadata only:** no behaviour change in the engine, hooks, skills or templates.
- **The scaffold's files stay unlicensed by this change:** no license header is added to the files `sdlc init`
  writes into users' repos.
- **Existing installs on beta.4 keep working:** `sdlc upgrade` changes only the pinned ref.
- **Tag and release after the merge only**, on the merge commit, and only because zoujagger asked for it
  (2026-11-25).
- **Approval commits are never rebased:** merge main, don't rebase.

## Out of scope
- Relicensing or re-tagging earlier releases; they stay MIT.
- Licensing terms for the files the scaffold writes into consumer repos (a separate decision if wanted).
- Intent 0006 (shell-parse residuals) and the earlier reviews' backlogs.
- Marketplace publication beyond the GitHub release.

## Open questions
- [ ] **The README status line for a non-beta 0.x:** proposed `**Status: 0.2.0.**` followed by a sentence saying
  the gates and file formats are stable within 0.2.x, and the CHANGELOG names every change. (zoujagger)
- [ ] **The release date:** the day the PR opens (2026-11-25), corrected before the merge if it lands later, as in
  0017. (zoujagger)
