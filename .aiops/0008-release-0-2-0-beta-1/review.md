---
id: 0008
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: e07d01934db66483c5538313fdc0b898844d89f8
score: 95/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-16
---

# Review: Release 0.2.0-beta.1

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Diff against origin/main (de5f520). -->

## Summary
The unreleased `0.2.0-alpha.4` becomes **0.2.0-beta.1** in every shipped file, and the alpha banners are reworded
for a beta. No behaviour changes.

Results:
- **Verifier:** VERIFIED, every AC met. `make check` (444), `make build` and `sdlc validate 0008` pass.
- **Code-reviewer:** PASS, no BLOCKER or MAJOR, four MINOR notes.
- **Security-reviewer:** PASS, 24/25, no CRITICAL or HIGH, one LOW (the accepted tag window).

**Verdict: PASS.**

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_shell_hooks.py:591 test_version_matches_changelog` (the version, the newest heading, the `v0.2.0-alpha.3...v0.2.0-beta.1` compare link); `tests/test_cli.py:951 Docs::test_changelog_has_the_release` |
| AC-2 | ✅ met | `tests/test_cli.py:937 Docs::test_no_shipped_file_names_alpha_4`; `git grep` outside `.aiops/` and `evals/results/` finds nothing |
| AC-3 | ✅ met | `tests/test_rules.py:326 History::test_current_scaffold_in_history`; the diff renames the key only, the hashes are unchanged |
| AC-4 | ✅ met | `tests/test_cli.py:928 Docs::test_release_banner_is_beta`; README pins at lines 58, 73, 107 |
| AC-5 | ✅ met | `git diff --name-only origin/main...HEAD`: the files R-1 to R-5 name, plus `tests/test_rules.py` (named in the plan's S1) and `.aiops/0008-*` |
| AC-6 | ✅ met (run quoted below) | `make check` OK (444); `make build` passes (warnings: no icon, root CLAUDE.md) |

**AC-6: the run** (plan.md Deviation log S3, 2026-11-16, `evals/results/2026-11-16T16-25-12-478Z`,
`--allow-tools Bash Write Edit`, 3 runs per arm): `profile-by-setup-command` 1.00 with the plugin
(asks-for-setup-command PASS ×3, config-unchanged ✓ ×3), 0.67 without, Δ +0.33, $0.88.

## Security
- [LOW] Between the merge and the tag, `v0.2.0-beta.1` doesn't exist; anyone with push access could create it on
  another commit first, and installs pinning it would load that code. → Tag right after the merge; better, protect
  `v*` with a tag ruleset. Same as every earlier release.

| Flag | Mitigated? | Evidence |
|---|---|---|
| The pins point at `v0.2.0-beta.1` before the tag exists | Partly, by process | spec Rollout: the human tags after the merge |
| No secret, approval, lock or audit path changes (R-6) | Yes | the only `lib/` change is one docstring line; hooks, schemas, scaffold templates and workflows untouched |

## Plan conformance
- S1-S3 are done and match the diff. Logged: S1 and S2 in one commit, the test needle built from parts, the
  widened README pin pattern, and S3's results.
- No out-of-scope change.

## Test-first evidence
`61fc571` names the five proof tests red on alpha.4, then `make check` green. S3 is verification only.

## Other findings (non-blocking)
- [MINOR] `CHANGELOG.md:8` is dated 2026-11-16; R-2 asks for the merge date. → Correct it if the merge is later.
- [MINOR] A repo scaffolded from untagged main may record `0.2.0-alpha.4`, no longer in the history; its files may
  read as stale until `sdlc upgrade` (spec Rollout; fail-safe, modified files are never touched).

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | Every AC met; AC-5 relies on the plan's file list for `tests/test_rules.py` |
| Security | 25 | 24 | The tag window |
| Test quality & test-first | 20 | 18 | Red recorded in the commit body |
| Plan conformance | 10 | 10 | All divergences logged |
| Maintainability | 5 | 5 | |
| **Total** | 100 | **95** | PASS: ≥ 80, no BLOCKER or HIGH, every AC met |
