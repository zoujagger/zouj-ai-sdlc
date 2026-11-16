---
id: 0008
title: Release 0.2.0-beta.1
status: Draft          # Draft → Approved (human types `Intent Approved 0008`) · Closed
owner: zoujagger
initiator: zoujagger (after PR #19 and #20 merged intent 0007)
source: the maintainer's decision to release 0.2.0-beta.1 (2026-11-16)
created: 2026-11-16
---

# Intent: Release 0.2.0-beta.1

<!-- State 1 BRAINSTORMING. Written from a targeted clarification interview. Unknowns go in Open questions,
     never invented. approved-* fields are stamped by the human approval; agents never write them. -->

## Problem
Intents 0005 (guard gaps) and 0007 (first run) are DONE on main, but nothing has been released since
`v0.2.0-alpha.3`. The tree says `0.2.0-alpha.4` (plugin.json, the CHANGELOG, the README pins, scaffold-history and
the tests that pin them), a version that was never tagged. A user installing from a tag gets alpha.3, without the
typed `/zouj-ai-sdlc:setup <profile>`, `sdlc where` or the core-only scaffold.

## Desired outcome
- The tree describes **0.2.0-beta.1** everywhere the version appears, and nothing names `0.2.0-alpha.4` as a
  release. The CHANGELOG's `[0.2.0-alpha.4]` section and scaffold-history's alpha.4 entry become beta.1, since
  alpha.4 never shipped.
- The CHANGELOG's "Alpha, experimental" banner reads as a beta (what may still change between betas).
- `make check` and `claude plugin validate .` pass, and the `profile-by-setup-command` eval passes when run at the
  release commit.
- After the merge, the human can tag `v0.2.0-beta.1` on the merge commit and the README's pins resolve.

## Users & systems affected
- Users: people installing the plugin from a tag or the marketplace; repos scaffolded by `sdlc init`/`setup` (their
  workflows pin the plugin at `v<version>`).
- Systems: `.claude-plugin/plugin.json`, `CHANGELOG.md`, `README.md` (and any other doc that pins the version),
  `defaults/scaffold-history.json`, the tests that pin the version, `lifecycle.py` if it names a release.

## Constraints
- A version bump only: no behaviour change in the engine, hooks or skills.
- Existing installs on alpha.3 keep working: `sdlc upgrade` moves them to beta.1 as it moved earlier alphas.
- The human tags and publishes; the agent never tags.

## Out of scope
- The 0007 backlog (the FIFO hang, the agent's `--with` under the read-only lock, `init --with` parsing, the
  `engine.sh` guard freeze, the TROUBLESHOOTING note, the test SyntaxWarnings): a later intent.
- Intent 0006 (shell-parse residuals).
- Tagging, the GitHub release and any marketplace publication (the human's steps).

## Open questions
None. The interview settled the alpha.4 rename and the scope (bump only).
