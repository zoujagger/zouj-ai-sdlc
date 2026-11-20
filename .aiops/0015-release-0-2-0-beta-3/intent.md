---
id: 0015
title: Release 0.2.0-beta.3
status: Approved
owner: zoujagger
initiator: zoujagger
source: request to release what 0011-0014 shipped, after the docs audit (PR #29), 2026-11-20
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T20:17:42Z
approved-via: cli
approved-sha256: 121bcb2b4eb25e0f78ee94f94948eab65ad664ca3e6cc86050884f4a0ae320e3
---

# Intent: Release 0.2.0-beta.3

<!-- State 1 BRAINSTORMING. Modeled on intent 0010 (the beta.2 release). The scope check passed: one workflow, a
     version bump. Unknowns go in Open questions, never invented. approved-* fields are stamped by the human
     approval; agents never write them. -->

## Problem
Four intents and a docs pass are on main but not in any release since `v0.2.0-beta.2`:
- **Scope sizing** (intent 0011, PR #25): the scope check, and the 5/8 AC limits on specs.
- **The opt-in `dsl` part** (0012, PR #26) and its **hardening** (0013, PR #27). They must ship together: 0013
  fixes 0012's activation by a bare `domain/`.
- **Sharper specs** (0014, PR #28): `None (no changes)`, the Mermaid cap, `[AC-N]` tags, query hygiene.
- **The docs audit** (PR #29), which describes all of the above.

A user who installs from a tag, or follows the README's pinned commands, gets beta.2 without any of them.

The tree still says `0.2.0-beta.2` in `plugin.json`, the README pins, the scaffold's rendered CI ref and the tests
that pin the version. The CHANGELOG holds the changes under `[Unreleased]`, and `defaults/scaffold-history.json`
records the changed templates as `unreleased`.

## Desired outcome
- **The tree describes 0.2.0-beta.3** everywhere a current version appears: `plugin.json`, the README pins (the
  status line, two marketplace commands and the settings snippet), and the tests that pin the release.
- **The CHANGELOG** has a dated `[0.2.0-beta.3]` section holding what is under `[Unreleased]` today, with the beta
  banner and a lead line naming 0011-0014 and the docs audit. `[Unreleased]` is left empty, and the compare links
  are updated.
- **Scaffold history:** the `unreleased` entry becomes `0.2.0-beta.3`, and the released entries are unchanged.
- **Checks pass** at the release commit: `make check`, `claude plugin validate .`, and `scaffold-history.py
  --check`.
- **After the merge**, the human can tag `v0.2.0-beta.3` on the merge commit, and the README's pins resolve.

## Users & systems affected
- **Users:**
  - people installing from a tag or the marketplace;
  - repos scaffolded by `sdlc init`/`setup`, whose workflows pin the plugin at `v<version>`, and whose
    `sdlc upgrade` moves them from beta.2. They get the new Makefile `validate-dsl` target, which stays dormant
    without the `dsl` part, and the updated templates.
- **Systems:** `.claude-plugin/plugin.json`, `CHANGELOG.md`, `README.md` (and any doc pinning the current
  version), `defaults/scaffold-history.json`, `docs/roadmap.md` if it lists these as upcoming, and the tests that
  pin the release (`tests/test_cli.py::Docs::test_changelog_has_the_release`,
  `tests/test_shell_hooks.py::…::test_version_matches_changelog`, `tests/test_rules.py::History`).

## Constraints
- **A version bump only:** no behaviour change in the engine, hooks, skills or templates.
- **Existing installs on beta.2 keep working:** `sdlc upgrade` moves them as it moved earlier releases. A Makefile
  wired by detection keeps its recipes (0012 S3, 0013 S2 tests).
- **The human tags and publishes;** the agent never tags.
- **Approval commits are never rebased:** merge main, don't rebase.

## Out of scope
- The non-blocking backlogs of the 0012, 0013 and 0014 reviews (validator wording, the Makefile and engine edge
  cases, `COMMENT_RE`, untested fence cases).
- Intent 0006 (shell-parse residuals).
- Recording the README demo GIF (`docs/demo/demo.tape`, still in your stash).
- Tagging, the GitHub release, and any marketplace publication (the human's steps).

## Open questions
- [x] **The release date:** the merge date, written with the day the PR opens (2026-11-20) and corrected before the
  merge if it lands later. (zoujagger, 2026-11-20)
- [x] **The docs audit (PR #29):** named in the lead line only; no `### Changed` entry. (zoujagger, 2026-11-20)
