---
id: 0017
title: Release 0.2.0-beta.4
status: Approved
owner: zoujagger
initiator: zoujagger
source: request to tag v0.2.0-beta.4 after intent 0016 merged (PR #31), 2026-11-21
created: 2026-11-21
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-21T12:07:13Z
approved-via: cli
approved-sha256: 3347589a53f2b02e1bbcff85e12b8cc66b7d8a8affc28fe801f86dbef9976feb
---

# Intent: Release 0.2.0-beta.4

<!-- State 1 BRAINSTORMING. Modeled on intent 0015 (the beta.3 release). The scope check passed: one workflow, a
     version bump. zoujagger chose a release intent before the tag (2026-11-21), because the tree still says
     beta.3. Unknowns go in Open questions, never invented. approved-* fields are stamped by the human approval;
     agents never write them. -->

## Problem
Intent 0016 (the intent skill reads the domain model and a PRD first, and starts from a clean `main`; PR #31) is on
main but in no release since `v0.2.0-beta.3`. Tagging main as it is would ship a `v0.2.0-beta.4` whose tree says
`0.2.0-beta.3`:

- `plugin.json` names beta.3, and `sdlc init` writes that version as the scaffold's CI pin (`ZOUJ_SDLC_REF`), so a
  repo set up from the beta.4 tag would have its CI fetch beta.3;
- the CHANGELOG holds 0016 under `[Unreleased]`;
- the README's status line, marketplace commands and settings snippet pin beta.3.

## Desired outcome
- **The tree describes 0.2.0-beta.4** everywhere a current version appears: `plugin.json`, the README pins (the
  status line, two marketplace commands and the settings snippet), and the tests that pin the release.
- **The CHANGELOG** has a dated `[0.2.0-beta.4]` section holding what is under `[Unreleased]` today, with the beta
  banner and a lead line naming 0016. `[Unreleased]` is left empty, and the compare links are updated.
- **Checks pass** at the release commit: `make check`, `claude plugin validate .`, and `scaffold-history.py
  --check`.
- **After the merge**, the merge commit is tagged `v0.2.0-beta.4` and published as a GitHub pre-release in the
  beta.3 format, at the human's request, and the README's pins resolve.

## Users & systems affected
- **Users:** people installing from a tag or the marketplace; repos scaffolded by `sdlc init`/`setup`, whose
  workflows pin the plugin at `v<version>`, and whose `sdlc upgrade` moves them from beta.3.
- **Systems:** `.claude-plugin/plugin.json`, `CHANGELOG.md`, `README.md`, and the tests that pin the release
  (`tests/test_cli.py::Docs::test_changelog_has_the_release`,
  `tests/test_shell_hooks.py::…::test_version_matches_changelog`). `defaults/scaffold-history.json` needs no
  change: 0016 changed no scaffold file (`scaffold-history.py --check` is up to date on main).

## Constraints
- **A version bump only:** no behaviour change in the engine, hooks, skills or templates.
- **Existing installs on beta.3 keep working:** no scaffold file changes, so `sdlc upgrade` has nothing new to write
  beyond the pinned ref.
- **Tag and release after the merge only**, on the merge commit, and only because zoujagger asked for it
  (2026-11-21).
- **Approval commits are never rebased:** merge main, don't rebase.

## Out of scope
- The non-blocking backlog of the 0016 review (literal `main`, PRD path resolution, DSL as data, the `!` wording,
  Step 2's layout).
- Intent 0006 (shell-parse residuals) and the earlier reviews' backlogs.
- Marketplace publication beyond the GitHub pre-release.

## Open questions
- [ ] **The release date:** the merge date, written as the day the PR opens (2026-11-21) and corrected before the
  merge if it lands later, as in 0015. (zoujagger)
