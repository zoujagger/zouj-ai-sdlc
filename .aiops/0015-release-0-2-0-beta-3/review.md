---
id: 0015
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 4a0c6f8f3a4b83d0fb3f93f7de51d8027c4e752f
score: 94/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-20
---

# Review: Release 0.2.0-beta.3

<!-- State 5 PRE-REVIEW. Written from the report of one fresh-context reviewer covering the three personas (a version
     bump), who got only the intent folder and the base branch `main` (8d61c72), plus 0010 for comparison. -->

## Summary
A version bump to 0.2.0-beta.3:
- `plugin.json`, and the README's status line and pins;
- the CHANGELOG: `[Unreleased]` moved byte for byte into `[0.2.0-beta.3] - 2026-11-20`, with the beta banner and a
  lead line naming 0011, 0012 with 0013, 0014 and PR #29;
- the scaffold history: `unreleased` renamed to `0.2.0-beta.3`, released entries unchanged;
- the tests that pin the release.

No behaviour changes. **PASS, 94/100**: every AC is met, and there is no BLOCKER and no CRITICAL/HIGH finding.

The reviewer ran, without writing anything:
- the targeted tests (Docs, version, History, Detected): 29 passed;
- `bin/sdlc validate --all`: 0 errors across 14 intents;
- `scaffold-history.py --check`: up to date;
- its own comparisons against `main`.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `.claude-plugin/plugin.json:3`; `CHANGELOG.md:8` (`## [0.2.0-beta.3] - 2026-11-20`, the newest); the links at `CHANGELOG.md:595-596`, the older ones unchanged; `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog` (`:603`), `tests/test_cli.py::Docs::test_changelog_has_the_release` (`:1235`) |
| AC-2 | ✅ met | The reviewer compared against `main:CHANGELOG.md`: the beta.3 `### Added` body equals main's `[Unreleased]` body byte for byte (2,874 bytes), and `[Unreleased]` is empty. The banner (`:10-11`) is word for word beta.2's, and the lead line (`:13-15`) names 0011, 0012 with 0013, 0014 and PR #29. `test_release_banner_is_beta` passes |
| AC-3 | ✅ met | The reviewer compared against `main:defaults/scaffold-history.json`: every released key (0.1.0 … 0.2.0-beta.2) is equal, `0.2.0-beta.3` equals main's `unreleased`, there is no `unreleased` key, and the key order is kept (a one-line rename). `--check` is up to date, and `test_rules.py::History` passes |
| AC-4 | ✅ met | `README.md:3`, `:55`, `:58`, `:101`; `tests/test_cli.py:1263-1265`. A tree-wide grep found no missed current-version pin: the other `beta.N` hits are history (`docs/lifecycle.md:29`, `docs/adoption.md:44`, `docs/roadmap.md:61,67`, `TROUBLESHOOTING.md:125,135`, `lib/sdlc_engine/lifecycle.py:223`), and the scaffold uses the `__ZOUJ_SDLC_REF__` placeholder |
| AC-5 | ✅ met | `git diff --name-only main...HEAD`: plugin.json, CHANGELOG.md, README.md, defaults/scaffold-history.json, tests/test_cli.py, tests/test_shell_hooks.py and `.aiops/0015-*`. `Detected::test_wired_makefile_keeps_recipes_with_validate_dsl` passes. `make check` 575 OK with `pipefail` (Deviation log, S2) |

## Security
None found. `v0.2.0-beta.3` doesn't exist yet (the accepted flag). Until it does, the README install and a scaffold's
CI fetch of its rendered `ZOUJ_SDLC_REF` (`aiops-gates.yml:29`) both fail closed, and only the repo owner can create
the tag.

Nothing else in the trust chain moves:
- **Code:** no engine, hook, template or schema change.
- **CI:** this repo's `ci.yml` still audits with the base branch's engine (`:52-55`).
- **`.claude-plugin/marketplace.json`** names no version (`source: "./"`).
- **The scaffold-history hashes** that `upgrade` uses to decide "untouched" are byte-identical to main's.

## Plan conformance
S1 and S2 were done as planned. There is one logged deviation, and the log is honest about it:
- **Four docs tests changed.** They now search everything above `[0.2.0-beta.2]` for their CHANGELOG entry.
- **The release commit `32f354f` was red.** The log names the cause (a `| tail` hid the exit code) and the fix
  commit, and S2 re-ran with `pipefail`.

Rule 6 is met: the deviation was logged in the fix commit `c84ae3b`. `docs/roadmap.md` needed no change.

## Test-first evidence
- **`53ebd84` changes only the tests:** the two version tests expect beta.3 while `plugin.json` still said beta.2,
  so the commit is red by construction (`'0.2.0-beta.2' != '0.2.0-beta.3'`).
- **`32f354f` is the release:** it turned those two green but broke the four docs tests.
- **`c84ae3b` fixes them.** It is disclosed in the Deviation log and in its own message.

The four test changes are sound:
- "Everything above `## [0.2.0-beta.2]`" means unreleased or shipped since beta.2. That holds before and after this
  release, and after later ones.
- `tests/test_cli.py:1200` (0009) already uses the same pattern against beta.1.
- The only check lost is "under `[Unreleased]` specifically", which was never true after a release.
- `test_changelog_has_the_release` now pins the beta.3 placement.

## Backlog (not blocking)
1. **A possible vacuous pass.** In `tests/test_cli.py:1013,1035,1061,1084`, if the `## [0.2.0-beta.2]` heading were
   renamed, `split(...)[0]` would return the whole file and the assertion would pass trivially.
   `test_changelog_has_the_release` would fail first, but an explicit `assertIn("\n## [0.2.0-beta.2]", log)` would
   make each test self-contained.
2. **The Deviation log's Commit column** says "S1 fix commit" and "S2" instead of the shas (`c84ae3b`, `4a0c6f8`).
3. **`32f354f` stays red in history,** a bisect hazard. Acceptable: it is disclosed, and approval commits are never
   rebased. Its own message doesn't mention the red state; only the follow-up does.
4. **The heading's date is 2026-11-20.** If the merge lands later, correct it and log it before the merge (R-2).

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 39 | every AC met |
| Security | 25 | 25 | no trust-chain change beyond the accepted tag flag |
| Test quality & test-first | 20 | 16 | the release commit was red (disclosed); a small vacuity edge in the four tests |
| Plan conformance | 10 | 9 | an unplanned test change, logged |
| Maintainability | 5 | 5 | |
| **Total** | 100 | **94** | PASS needs ≥ 80, no BLOCKER, every AC met |
