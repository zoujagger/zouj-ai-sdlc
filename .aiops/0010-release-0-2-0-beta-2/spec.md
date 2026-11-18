---
id: 0010
title: Release 0.2.0-beta.2
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-18
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-18T13:23:46Z
approved-via: cli
approved-sha256: adf8daa139b6185d84efa9f57ade1e14a13633e85d4b4b93a91a80ac05e90536
---

# Spec: Release 0.2.0-beta.2

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements. Modeled on 0008's spec. Policy skills applied (security, compliance). -->

## Summary
These changes are on main but not in any release since `v0.2.0-beta.1`:
- stack auto-detection (intent 0009, PR #23);
- the README funnel and the new docs pages (PR #22).

This change bumps the current version to **0.2.0-beta.2**:
- in `plugin.json`;
- in the README pins;
- in the tests that pin the current release.

It also does these:
- turns the CHANGELOG's `[Unreleased]` entries into a dated `[0.2.0-beta.2]` section;
- renames scaffold-history's `unreleased` entry to `0.2.0-beta.2`.

After the merge the human tags `v0.2.0-beta.2`, and installs from the tag get detection. Nothing changes in
behaviour (intent: Desired outcome, Constraints).

## Requirements
- **R-1:** `.claude-plugin/plugin.json` `version` is `0.2.0-beta.2`. `.claude-plugin/marketplace.json` names no
  version and isn't touched.
- **R-2: the CHANGELOG.**
  - **The new section:** what is under `## [Unreleased]` today (`### Added`, `### Fixed`, `### Changed`) moves,
    unchanged, into a new `## [0.2.0-beta.2] - <date>` section placed above `## [0.2.0-beta.1]`.
  - **The date:** the merge date (the human's choice). The section is written with the day the PR is opened
    (2026-11-18). If the merge happens on a later day, the heading is corrected in the PR before the merge, as a
    logged deviation.
  - **Its banner and lead:** the section opens with the beta banner, worded as in beta.1, then one line that names
    what ships:
    - `.aiops/0009-stack-detection/`;
    - the README funnel (PR #22).
  - **`[Unreleased]`** stays as an empty heading.
  - **The link references** become:
    - `[Unreleased]: …/compare/v0.2.0-beta.2...HEAD`
    - `[0.2.0-beta.2]: …/compare/v0.2.0-beta.1...v0.2.0-beta.2`
    - The older links are unchanged.
- **R-3: the scaffold history.** In `defaults/scaffold-history.json`, the `unreleased` entry becomes
  `0.2.0-beta.2`, with the same hashes. `python3 scripts/scaffold-history.py` does this once `plugin.json` says
  beta.2, since that version has no tag yet. The released entries (0.1.0 … 0.2.0-beta.1) are unchanged.
- **R-4: the README pins** name `v0.2.0-beta.2`:
  - the status line: `beta (0.2.0-beta.2)`;
  - both `marketplace add …@v0.2.0-beta.2` commands;
  - the settings snippet's `"ref"`.

  Mentions of beta.1 as history stay as they are (TROUBLESHOOTING "Since 0.2.0-beta.1", `docs/lifecycle.md`,
  `docs/adoption.md`, the `lifecycle.py` docstring, test comments).

  `docs/roadmap.md`'s "Adoption, part 2" entries say they shipped in 0.2.0-beta.2.
- **R-5: the tests that pin the current release.**
  - `tests/test_shell_hooks.py::…::test_version_matches_changelog` and `tests/test_cli.py::Docs::test_changelog_has_the_release`
    expect `0.2.0-beta.2`.
  - `test_changelog_has_the_release` checks the beta.2 section for:
    - `.aiops/0009-stack-detection/`;
    - `--stack auto`;
    - the README funnel.

    It keeps its checks that `[Unreleased]` holds no "Planned as", that the compare link is right, and that every
    README pin matches `plugin.json`. Its round-1 relaxation (an `unreleased` history entry is allowed while
    `[Unreleased]` has entries) then demands no `unreleased` key, since `[Unreleased]` is empty.
  - `tests/test_rules.py::History` keeps asserting the beta.1 entry, and passes with the new beta.2 entry.
- **R-6: nothing else changes.**
  - No engine, hook, skill, template or schema behaviour changes.
  - Generated eval results (`evals/results/*`) are records and keep their version strings.
- **Non-functional:** `make check` and `claude plugin validate .` pass.

## Acceptance criteria
- **AC-1**: Given the release, when `plugin.json` is read, then `version` is `0.2.0-beta.2`, and the newest
  CHANGELOG release heading is `[0.2.0-beta.2] - <date>`, with the compare link from `v0.2.0-beta.1`
  (`test_version_matches_changelog`, `test_changelog_has_the_release`).
- **AC-2**: Given the CHANGELOG, then `[Unreleased]` has no entries, and the beta.2 section holds, unchanged, the
  `### Added`, `### Fixed` and `### Changed` entries that `[Unreleased]` held on main at 992c725. Its banner doesn't
  say "alpha" (`test_release_banner_is_beta`).
- **AC-3**: Given `defaults/scaffold-history.json`, then:
  - it has a `0.2.0-beta.2` entry with the hashes the `unreleased` entry had;
  - it has no `unreleased` key;
  - the released entries are byte-identical to main's;
  - `scripts/scaffold-history.py --check` reports it up to date;
  - `History::test_current_scaffold_in_history` passes.
- **AC-4**: Given the README, then the status line and every pin name `0.2.0-beta.2`, and no other version string
  appears above `## Lifecycle` (`test_changelog_has_the_release`).
- **AC-5**: Given the change, when `git diff --name-only origin/main` is read, then only these files have changed:
  - the files R-1 to R-5 name (`plugin.json`, `CHANGELOG.md`, `README.md`, `docs/roadmap.md`,
    `defaults/scaffold-history.json`, and the three test files);
  - `.aiops/0010-*`.
- **AC-6**: Given the release commit, then `make check` and `claude plugin validate .` pass, and a run of the
  `profile-by-setup-command` eval with the plugin scores 1.00 on its graders. The run is quoted in review.md.
- **AC-7**: Given a repo scaffolded by 0.2.0-beta.1 (its Makefile wired by the `python` preset, no `recipes` in
  install-state), when the beta.2 plugin runs `sdlc upgrade --dry-run`, then it plans to replace only the files whose
  template changed, and the Makefile is planned with its preset recipes kept
  (`tests/test_lifecycle.py::Detected::test_beta1_state_unchanged` keeps passing; no new test).

## Data model
None. Text files only.

## API contracts
None. No command, flag, hook or file format changes.

## Security & data-leak flags
- ⚠️ **The pins point at a tag that doesn't exist yet.** The README pins and the scaffold's rendered
  `ZOUJ_SDLC_REF` point at `v0.2.0-beta.2`, which won't exist until the human creates it, as with every release
  so far. Mitigation: the human tags right after the merge (Rollout). (zoujagger)
- No secret, approval, lock or audit path changes (R-6).

## Architecture
- **Where the version lives:** in `plugin.json`. `cli.plugin_version()` reads it, and from it come:
  - the scaffold's rendered ref (`cli.rendered_template`, `v<version>`);
  - the agent's `upgrade` pins;
  - install-state's `plugin_version`.
- **The history lookup:** `lifecycle.history_key()` finds the running version in `defaults/scaffold-history.json`.
  R-3 keeps that true: the key becomes `0.2.0-beta.2`.
- **Not taken:** keeping the `unreleased` history key until the tag exists. The 0008 release test, kept by 0009,
  requires no `unreleased` key at a release.

## Rollout & rollback
- **Rollout:**
  1. One PR.
  2. After it merges, the human tags `v0.2.0-beta.2` on the merge commit and pushes the tag, which drafts the
     GitHub release.
  3. The human then publishes the release.
- **Upgrades:** repos on beta.1 move with `sdlc upgrade`. It re-pins the scaffold ref and replaces the unmodified
  Makefile template, whose header changed in 0009, keeping recorded or preset recipes.
- **Rollback:** revert the PR, and delete the tag if one was pushed.

## Open questions
None. The intent's question (the CHANGELOG date) was answered: the merge date.
