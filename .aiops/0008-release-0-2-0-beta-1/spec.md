---
id: 0008
title: Release 0.2.0-beta.1
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-16
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-16T16:17:20Z
approved-via: cli
approved-sha256: 19809af2c97184debec30d1136de2a2f025244878f20780536960bb58976de99
---

# Spec: Release 0.2.0-beta.1

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements, DB schema and API contracts. Policy skills applied (security, compliance, UX, brand). -->

## Summary
Intents 0005 and 0007 are DONE on main, but the last tag is `v0.2.0-alpha.3`, and the tree names
`0.2.0-alpha.4`, which was never tagged. This change renames that unreleased version to **0.2.0-beta.1**
everywhere the shipped files carry it, and rewords the alpha banners for a beta. The human can then tag
`v0.2.0-beta.1`, and installs get the typed `/zouj-ai-sdlc:setup <profile>`, `sdlc where` and the core-only
scaffold. No behaviour changes (intent: Desired outcome, Constraints).

## Requirements
- **R-1**: `.claude-plugin/plugin.json` `version` is `0.2.0-beta.1`.
- **R-2**: CHANGELOG: the `## [0.2.0-alpha.4] - 2026-11-13` section becomes `## [0.2.0-beta.1] - <the merge date>`
  and keeps its content. The link references at the bottom become
  `[Unreleased]: …/compare/v0.2.0-beta.1...HEAD` and `[0.2.0-beta.1]: …/compare/v0.2.0-alpha.3...v0.2.0-beta.1`.
  `[0.2.0-alpha.4]` appears nowhere. The section's "Alpha, experimental" banner reads as a beta: the workflow,
  gates and file formats are settling, but may still change between betas.
- **R-3**: `defaults/scaffold-history.json`: the `"0.2.0-alpha.4"` key becomes `"0.2.0-beta.1"`, with the same
  hashes. Regenerate with `python3 scripts/scaffold-history.py` if it gives the same bytes, otherwise rename the key
  by hand.
- **R-4**: Every pin and version mention in shipped docs that names alpha.4 names beta.1 instead:
  - README: the status line (reworded from "alpha … between alphas" to beta), "current release", the
    `marketplace add …@v0.2.0-beta.1` lines, the settings `"ref"`, and the install-state note.
  - TROUBLESHOOTING.md, docs/adoption.md and docs/roadmap.md: "Since 0.2.0-alpha.4" and "alpha.4" mentions.
  - The `lifecycle.py` docstring that names the version.
- **R-5**: The tests that pin the version (`tests/test_cli.py` `test_changelog_has_the_release`,
  `tests/test_shell_hooks.py` `test_version_matches_changelog`) expect `0.2.0-beta.1`.
- **R-6**: Nothing else changes. No engine, hook, skill, template or schema behaviour changes, except the
  docstring in R-4. Generated eval results (`evals/results/*`) are records and keep their old version strings.
- Non-functional: `make check` and `claude plugin validate .` pass.

## Acceptance criteria
- **AC-1**: Given the release, when `plugin.json` is read, then `version` is `0.2.0-beta.1`, and the newest
  CHANGELOG release heading is `[0.2.0-beta.1]` with the compare link from `v0.2.0-alpha.3`
  (`test_version_matches_changelog`, `test_changelog_has_the_release`).
- **AC-2**: Given the shipped files (everything outside `.aiops/`, `evals/results/` and `.git/`), when they are
  searched for `0.2.0-alpha.4` and `alpha.4`, then nothing is found.
- **AC-3**: Given `defaults/scaffold-history.json`, then it has a `0.2.0-beta.1` entry with the hashes the alpha.4
  entry had, no `0.2.0-alpha.4` key, and `History::test_current_scaffold_in_history` passes.
- **AC-4**: Given the README, then every pin is `v0.2.0-beta.1`, and neither its status line nor the CHANGELOG
  section's banner says "alpha".
- **AC-5**: Given the change, when `git diff` is read against main, then only the files R-1 to R-5 name, plus
  `.aiops/0008-*`, have changed.
- **AC-6**: Given the release commit, then `make check` and `claude plugin validate .` pass, and a run of the
  `profile-by-setup-command` eval with the plugin passes. The run is quoted in review.md.

## Data model
None. Text files only.

## API contracts
None. No command, flag, hook or file format changes.

## Security & data-leak flags
- ⚠️ The README pins and the scaffold's `ZOUJ_SDLC_REF` point at `v0.2.0-beta.1`, a tag that won't exist until the
  human creates it, as with every release so far. Mitigation: the human tags right after the merge (Rollout).
  (owner)
- No secret, approval, lock or audit path changes (R-6).

## Architecture
- The version lives in `plugin.json`. `cli.plugin_version()` reads it, and from it come the scaffold's rendered
  ref (`cli.rendered_template`, `v<version>`) and install-state's `plugin_version`.
- `lifecycle.history_key()` must find the running version in `defaults/scaffold-history.json`; R-3 keeps that true.
- Alternative not taken: keep `[0.2.0-alpha.4]` and add a beta.1 section. The human chose the rename, because
  alpha.4 never shipped (interview).

## Rollout & rollback
- One PR. After it merges, the human tags `v0.2.0-beta.1` on the merge commit and pushes the tag, which drafts the
  GitHub release, then publishes the release.
- Repos on alpha.3 move with `sdlc upgrade` (it re-pins the scaffold ref to `v0.2.0-beta.1`).
- A repo scaffolded from an untagged main between the two releases may record `0.2.0-alpha.4` in install-state.
  That version is no longer in the history, so `sdlc list-installed` may call its files stale; `sdlc upgrade` sets
  them right.
- Rollback: revert the PR, and delete the tag if one was pushed.

## Open questions
None.
