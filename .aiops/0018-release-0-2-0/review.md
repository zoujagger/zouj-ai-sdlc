---
id: 0018
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: e7b6177
score: 96/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-25
---

# Review: Release 0.2.0

<!-- State 5 PRE-REVIEW. Unlike 0017, this review was written in the implementing session, not by a fresh-context
     reviewer: the three personas' checklists were applied to the diff `main...e7b6177` (main = fea5b57) and every
     result below was re-run, not recalled. The human may ask for a fresh-context review before merging. -->

## Summary
The release bumps the current version to 0.2.0 and the declared license to AGPL-3.0-or-later, matching the LICENSE
file that PR #36 merged: `plugin.json`, the README (status line, four pins, a new License section), a dated
CHANGELOG section without the beta banner, a scaffold-history entry equal to beta.4's, and the release tests. No
engine, hook, skill, template or schema behaviour changes. **PASS, 96/100**: every AC is met, no BLOCKER and no
CRITICAL/HIGH/MEDIUM finding.

Re-run: `make check` (576 tests OK, 3 skipped); `make validate` (passed, one existing warning: root `CLAUDE.md`);
`scaffold-history.py --check` (up to date); `bin/sdlc validate --all` (17 intents, 0 errors; the old AC-count
warning on 0010 only).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `.claude-plugin/plugin.json:3` `0.2.0`, `:10` `AGPL-3.0-or-later`; `CHANGELOG.md:8` `## [0.2.0] - 2026-11-25`, the newest release; compare link from `v0.2.0-beta.4` (`:628`); `test_shell_hooks.py::ShellHooks::test_version_matches_changelog`, `test_cli.py::Docs::test_changelog_has_the_release` pass |
| AC-2 | ✅ met | `[Unreleased]` empty (`CHANGELOG.md:6`); the 0.2.0 section has no `>` banner, a lead line, `### Changed` (AGPL-3.0-or-later from 0.2.0, MIT up to beta.4) and `### Added` (demo GIF, Quick start, PRs #33-#35); `test_changelog_has_the_release` and `test_release_banner_is_not_prerelease` pass |
| AC-3 | ✅ met | `README.md:3` `**Status: 0.2.0.**` (no alpha/beta); pins at `:57`, `:65`, `:74`, `:146` name `v0.2.0`; no `0.2.0-(alpha\|beta\|rc).N` above `## Lifecycle`; `## License` at `:212` names AGPL-3.0-or-later, `LICENSE` and MIT; asserted by both tests |
| AC-4 | ✅ met | the `0.2.0` history entry equals beta.4's; every entry of `main:defaults/scaffold-history.json` is identical; no `unreleased` key; `git diff --name-only main...HEAD` lists only S1's files and `.aiops/0018-*`; `make check`, `make validate`, `scaffold-history.py --check` pass |

**Bump completeness:** every remaining `0.2.0-beta.4` outside `.aiops/` is history and correctly kept (the beta.4
heading and compare links, the License notes, the beta.4 slice in the release test, the released history key). No
version is hard-coded in `templates/`, `skills/`, `agents/`, `hooks/` or `lib/`; the CI workflows use the
`__ZOUJ_SDLC_REF__` placeholder that `sdlc init` fills from `plugin.json`. `MIT` no longer appears in any shipped
manifest.

## Security
None found. No engine, hook, guard, approval, secret-path or CI-audit file changed; the only moving part is the ref
`sdlc init` writes and `upgrade` pins (`v<version>`), as intended.

Spec flags:
- **Pins to a tag that doesn't exist yet:** an install from the README fails closed until R-7 tags right after the
  merge.
- **License mix-up:** mitigated. Manifest, README, CHANGELOG all say AGPL-3.0-or-later and a test pins the SPDX id.
  [NIT] PR #36's own commit `07f1ede` still says "GPL-3.0" in its message; it can't change without a rewrite of
  main, and its merge commit `fea5b57` states AGPL-3.0-or-later.
- **Unsigned tag**, as the betas: accepted; the signed approvals and the CI audit are the guarantee.

The three approval commits (29cdfdb, 7820cea, f519740) each touch one file, carry an `AIOps-Approval` trailer with
the matching digest, and are signed.

## Plan conformance
- S1 changed every planned file as described and nothing else; S2's commands and results are in the Deviation log.
- R-7 (tag, release) is kept out of the steps, as planned.
- [NIT] The README status line says "artifact formats" where the intent's question said "file formats"; same meaning.

## Test-first evidence
| Step | Red (tests only) | Green |
|---|---|---|
| S1 | e07a287 (`tests/test_cli.py`, `tests/test_shell_hooks.py`; fail `'0.2.0-beta.4' != '0.2.0'` and on the beta banner) | d070606 (`plugin.json`, CHANGELOG, README, scaffold history) |
| S2 | n/a (verification) | e7b6177 (`plan.md` ticks and Deviation log only) |

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 40 | every AC met; every current pin bumped, history kept |
| Security | 25 | 25 | trust model unchanged; spec flags handled |
| Test quality & test-first | 20 | 18 | red commit before the bump; the lead line isn't asserted |
| Plan conformance | 10 | 10 | file-by-file; verification logged |
| Maintainability | 5 | 3 | review written in the implementing session, not fresh context |
| **Total** | 100 | **96** | PASS needs ≥ 80, no BLOCKER, every AC met |
