---
id: 0017
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 02ec52a
score: 98/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-21
---

# Review: Release 0.2.0-beta.4

<!-- State 5 PRE-REVIEW. Written from the report of one fresh-context reviewer covering the three personas, who got
     only the intent folder and the base branch `main` (e86010b). -->

## Summary
The release bumps the current version to 0.2.0-beta.4: `plugin.json`, the four README pins, the two release tests,
a dated CHANGELOG section holding 0016's entry unchanged, and a scaffold-history entry equal to beta.3's. No
engine, hook, skill, template or schema behaviour changes. **PASS, 98/100**: every AC is met, and there is no
BLOCKER and no CRITICAL/HIGH/MEDIUM finding.

The reviewer re-ran, without writing anything: `test_cli.Docs` with `test_version_matches_changelog` (17 OK);
`scaffold-history.py --check` (up to date); `bin/sdlc validate --all` (16 intents, 0 errors; the old AC-count
warnings on 0007-0010 only); `bin/sdlc status` (state 5, gates open, Steps 2/2).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `.claude-plugin/plugin.json:3` `0.2.0-beta.4`; `CHANGELOG.md:8` `## [0.2.0-beta.4] - 2026-11-21`, the newest release; the compare link from `v0.2.0-beta.3` (`:612`); `test_shell_hooks.py::ShellHooks::test_version_matches_changelog` and `test_cli.py::Docs::test_changelog_has_the_release` pass |
| AC-2 | ✅ met | `git diff e86010b HEAD -- CHANGELOG.md` adds only the heading, banner, lead line and two links; the 0016 `### Changed` entry is untouched and `[Unreleased]` is empty; the banner matches beta.3's word for word; the test asserts 0016 is in the beta.4 section |
| AC-3 | ✅ met | README pins at lines 3, 55, 58 and 101 say beta.4; no other version string above `## Lifecycle`; the test asserts the version set, the two `@v{version}` commands and the `"ref"` |
| AC-4 | ✅ met | the `0.2.0-beta.4` history entry equals beta.3's; every entry of `main:defaults/scaffold-history.json` is identical; no `unreleased` key; `git diff --name-only main...HEAD` lists only S1's files and `.aiops/0017-*`; `make check` OK (576, 3 skipped) and `make validate` passed (Deviation log, S2) |

**Bump completeness:** every remaining `0.2.0-beta.3` outside `.aiops/` is history and correctly kept (the beta.3
heading and compare links, the 0016 guidance test's boundary, the new beta.3 slice in the release test, the
released history key). No version is hard-coded in `templates/`, `skills/`, `agents/`, `hooks/` or `lib/`; the CI
workflows use the `__ZOUJ_SDLC_REF__` placeholder that `sdlc init` fills from `plugin.json`.

## Security
None found. The trust model is unchanged: no engine, hook, guard, approval, secret-path or CI-audit file changed.
The only moving part is the ref `sdlc init` writes and `upgrade` pins (`v<version>`), as intended.

Spec flags:
- **Pins to a tag that doesn't exist yet:** an install from the README fails closed until R-7 tags right after the
  merge.
- **Unsigned tag**, as beta.1-beta.3: accepted; the signed approvals and the CI audit are the guarantee.

The approval commits each touch one file and carry the `AIOps-Approval` trailer. The spec was approved twice
(d6f3c21, then 953fe06): it was re-drafted to move the tag AC into Rollout, as its header comment says.

## Plan conformance
- S1 changed every planned file as described, and nothing else; S2's commands and results are in the Deviation log.
- CLAUDE.md rule 6 is satisfied; R-7 (tag, pre-release) is correctly kept out of the steps.
- [NIT] intent.md's Systems line says `scaffold-history.json` needs no change; spec R-3 corrects it explicitly, so
  no plan deviation is needed.

## Test-first evidence
| Step | Red (tests only) | Green |
|---|---|---|
| S1 | 3661f94 (`tests/test_cli.py`, `tests/test_shell_hooks.py`; both fail `'0.2.0-beta.3' != '0.2.0-beta.4'`) | 1433876 (`plugin.json`, CHANGELOG, README, scaffold history, plan tick) |
| S2 | n/a (verification) | 02ec52a (`plan.md` Deviation log only) |

The reviewer checked the red commit by inspection (at 3661f94 `plugin.json` says beta.3 and both tests assert
beta.4); replaying it in a scratch extract wasn't permitted.

Findings (none blocking):
- [LOW] `tests/test_cli.py:1267-1268`: no assertion on the beta.4 banner or the "unchanged" lead line, so AC-2's
  banner and lead rest on the diff → assert `> **Beta.**` and "unchanged" in each release section (Backlog 1).
- [LOW, process] `CHANGELOG.md:8`: the date is 2026-11-21; if the merge lands later, correct it before the merge and
  log it (spec R-2) (Backlog 2).

## Backlog (not blocking)
1. One test that every release section carries the beta banner and an "… unchanged" lead line.
2. Check the CHANGELOG date at merge time.
3. After the merge, R-7's check: `git rev-parse v0.2.0-beta.4^{commit}` equals the merge commit, and
   `gh release view v0.2.0-beta.4` shows a pre-release.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 40 | every AC met; every current pin bumped, history kept |
| Security | 25 | 25 | trust model unchanged; spec flags handled |
| Test quality & test-first | 20 | 18 | red commit before the bump; no banner/lead assertion; red checked by inspection |
| Plan conformance | 10 | 10 | file-by-file; verification logged |
| Maintainability | 5 | 5 | |
| **Total** | 100 | **98** | PASS needs ≥ 80, no BLOCKER, every AC met |
