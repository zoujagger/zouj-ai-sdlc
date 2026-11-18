---
id: 0010
title: Release 0.2.0-beta.2
status: Approved
owner: zoujagger
initiator: zoujagger (after PR #22 and PR #23 merged)
source: the maintainer's decision to release 0.2.0-beta.2 (2026-11-18)
created: 2026-11-18
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-18T13:22:20Z
approved-via: cli
approved-sha256: eff472e766996a1e61806169576e3b74bb6bbb11d164dccff76de3c6fb59ddd3
---

# Intent: Release 0.2.0-beta.2

<!-- State 1 BRAINSTORMING. Modeled on intent 0008 (the beta.1 release). Unknowns go in Open questions, never
     invented. approved-* fields are stamped by the human approval; agents never write them. -->

## Problem
Two changes are on main but not in any release since `v0.2.0-beta.1`:
- **Stack auto-detection** (intent 0009, PR #23).
- **The README funnel and the new docs pages** (PR #22).

A user who installs from a tag, or follows the README's pinned commands, gets beta.1, which has no detection.

The tree still says `0.2.0-beta.1` in these places:
- `plugin.json`;
- the README pins;
- the scaffold's CI ref;
- the tests that pin the version.

The CHANGELOG holds these changes under `[Unreleased]`, and `defaults/scaffold-history.json` records the changed
Makefile template as `unreleased`.

## Desired outcome
- **The tree describes 0.2.0-beta.2** everywhere a current version appears:
  - `plugin.json`;
  - the README and doc pins (two marketplace commands and the settings snippet);
  - the tests that pin the release.
- **The CHANGELOG** has a dated `[0.2.0-beta.2]` section holding what is under `[Unreleased]` today, with the beta
  banner. `[Unreleased]` is left empty, and the compare links are updated.
- **Scaffold history:** `defaults/scaffold-history.json`'s `unreleased` entry becomes `0.2.0-beta.2`, and the
  released entries are unchanged.
- **Checks pass:** `make check` and `claude plugin validate .`, and the `profile-by-setup-command` eval when run at
  the release commit.
- **After the merge**, the human can tag `v0.2.0-beta.2` on the merge commit, and the README's pins resolve.

## Users & systems affected
- **Users:**
  - people installing the plugin from a tag or the marketplace;
  - repos scaffolded by `sdlc init`/`setup`, whose workflows pin the plugin at `v<version>`, and whose
    `sdlc upgrade` moves them from beta.1.
- **Systems:**
  - `.claude-plugin/plugin.json` (and the marketplace manifest, if it names the version);
  - `CHANGELOG.md`, `README.md` and any other doc that pins the current version;
  - `defaults/scaffold-history.json`;
  - the tests that pin the release (`tests/test_cli.py::Docs`, `tests/test_rules.py::History`, the version test in
    `tests/test_shell_hooks.py`).

## Constraints
- **A version bump only:** no behaviour change in the engine, hooks or skills.
- **Existing installs on beta.1 keep working:** `sdlc upgrade` moves them to beta.2 as it moved earlier releases. A
  Makefile wired by a beta.1 preset stays `current` (0009 AC-20).
- **The human tags and publishes;** the agent never tags.
- **Approval commits are never rebased:** merge main, don't rebase.

## Out of scope
- The 0009 review backlog (the `_java` note wording, an `id` split over lines in Gradle files).
- Intent 0006 (shell-parse residuals, including the env-stripped `sdlc init` in a repo without `.aiops/`).
- Recording the README demo GIF.
- Tagging, the GitHub release and any marketplace publication (the human's steps).

## Open questions
- [ ] Release date for the CHANGELOG heading: the merge date (as for beta.1), or a date the human names?
      (zoujagger)
