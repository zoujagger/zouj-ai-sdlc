---
id: 0003
verdict: PASS
commit: 42bc90383f5ba47ffd490e536c7b5aa4abb2fca2
score: 85/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 8

<!-- State 5 PRE-REVIEW, round 8 (after L1–L4). Compiled only from the three fresh-context persona reports (base main
     @ 429614a, head 42bc903). Rounds 1–7 (76, 80, 78, 84, 89, 90, 85) are in git history. The human decides what
     happens next. -->

## Summary
- **Verifier:** VERIFIED. 15/15 ACs. The L1–L4 proof tests are red on their parents.
- **Code reviewer:** every AC met, no BLOCKER or HIGH. 1 MEDIUM, 1 MINOR-to-MEDIUM, and LOW/MINOR items.
- **Security reviewer:** PASS, 20/25. 1 MEDIUM, 3 LOW.
- **Checks:** `make check` (168 tests), `make build` and `sdlc validate 0003` pass.
- **L1–L4 hold for what they targeted:**
  - L1: protected paths are kept when unlocked, and it correctly corrects K1.
  - L2: `CLAUDE_PROJECT_DIR=` and `HOME=` are refused.
  - L3: a planted, unstaged signer is shown and left out of the commit list.
  - L4: the downgrade label.

Verdict: **PASS, 85/100** by the rule. Two of the open MEDIUMs were introduced by round-7 fixes:
- **[MEDIUM] L3's commit step commits the whole index** (security). The printed command is
  `git add -- <files> && git commit -m …`. A plain `git commit` takes everything staged, so an `allowed-signers` key
  the agent staged with `git hash-object -w` + `git update-index --cacheinfo` rides along, while the working tree still
  equals HEAD and no review section appears. `unreviewed()` compares only the working tree with HEAD. The first
  adoption PR has no CODEOWNERS on base, so a human merge makes CI trust the key. L3's "commit exactly what setup
  wrote" doesn't hold yet.
- **[MEDIUM] L2's command-position match reopened K2's cross-repo bypass** (code). The relocation check runs only
  when `sdlc init|setup` sits in command position. `cd ../other && echo 'sdlc init' | sh`, `bash <<< '…'`,
  `setarch … sdlc init` (or `prlimit`, `chronic`, `uv run`, `npx`) and `sh x.sh` all pass. The parent 6d1a895
  blocked them, and `cd O && sh -c 'echo "…sdlc init" | sh'` scaffolds O end to end.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:114`; under a real tty by hand |
| AC-2 | ✅ met | `tests/test_setup.py:190` (status reads "No intents yet"; read-only through the pre-edit hook) |
| AC-3 | ✅ met | `tests/test_setup.py:218` (a rerun before committing floods `!` rows: F2 below) |
| AC-4 | ✅ met | `tests/test_setup.py:244`, `:257`, `:277`, `:294` |
| AC-5 | ✅ met | `tests/test_setup.py:383`, `:309` |
| AC-6 | ✅ met | `tests/test_setup.py:128` |
| AC-7 | ✅ met | `tests/test_engine.py:530`, `:500`, `:392`; `tests/test_playbook.py` |
| AC-8 | ✅ met | `tests/test_playbook.py:135-141` |
| AC-9 | ✅ met | `tests/test_cli.py:96` |
| AC-10 | ✅ met | `tests/test_setup.py:696`, `:708` |
| AC-11 | ✅ met | `tests/test_setup.py:80` |
| AC-12 | ✅ met | `tests/test_shell_hooks.py:309` |
| AC-13 | ✅ met | `tests/test_setup.py:722` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:340`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:190`, `tests/test_setup.py:190` |

## Security
- **[MEDIUM] A staged trust file rides along with setup's commit step** (`setup.py:450-453`, `:200-210`).
  - Fix: print `git commit -m … -- <files>`, so only those paths are committed.
  - Flag human-owned files whose index differs from HEAD (`git diff --cached --quiet HEAD`).
  - List any other staged path.
  - Separately, the guard allows index plumbing (`hash-object -w`, `update-index --cacheinfo`, `git add`) on
    protected paths. That gap predates this branch.
- **[MEDIUM] L2 regression: piped, here-string and unlisted-runner forms pass the scaffold rule**
  (`guards.py:373-381`).
  - Fix: when a relocation form is present, fall back to the whole-line `sdlc init|setup` match. Add the forms to the
    test.
- **[LOW]** Brace-expanded `{cd,/x}` and `unset CLAUDE_PROJECT_DIR` aren't relocation forms (`guards.py:377`).
- **[LOW]** Planted file contents reach the terminal unescaped in the review diffs (`setup.py:329`, `:336`), so control
  sequences can hide a line.
- **[LOW]** Doctor's CODEOWNERS ✓ ignores a later owner-less rule under `/.aiops/` (`cli.py` `codeowners_cover_aiops`).
  CI is unaffected.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes**, stated |
| Setup writing `.claude/settings.json` | **yes** |
| Profile changes through setup | **yes**, locally a deterrent |
| `gh auth status` / `claude --version` | **yes** |
| No sandbox; setup writes only in its repo | **partially**: piped and unlisted-runner forms, brace-`cd` (MEDIUM, LOW) |
| `sdlc feedback` | **yes** |

## Plan conformance
- S1–S15 are ticked, and K1–K3 and L1–L4 are logged.
- L1's correction of K1 is accurate.
- **Inaccurate:**
  - L2's residual list (and the `docs/architecture.md` row) omits what the narrowing reopened.
  - L3 says "the list is taken once", but it is taken twice, both before writing (harmless).
- The CHANGELOG known issues are accurate, two of them approximately (signing steps; `.gitignore`).

## Other findings (code reviewer)
- **[MINOR-to-MEDIUM] F2: a rerun before the commit misreports setup's own files** (`setup.py:200-210`, `:227`,
  `:349`, `:450`).
  - In the documented agent → human flow, and after any second run, all 18 human-owned files show `!` "setup didn't
    write it", and there is **no commit step**.
  - Fix: word the note neutrally ("not in any commit yet"), and always print a commit step for every uncommitted
    scaffold file not under review. Add rerun tests.
- **[LOW] F3:** `pwd.getpwuid` raises `KeyError` for a uid with no passwd entry (containers), so init and setup show a
  traceback (`cli.py:328`).
- **[LOW] F4:** a non-UTF-8 planted file crashes the review diff, dry run included (`setup.py:336`).
- **[LOW] F5:** L1's secret-paths branch is untested, and dead with the defaults.
- **[MINOR] F6:** TROUBLESHOOTING and the setup skill (step 3) don't mention the plan's `!` rows or the review
  section.
- **[MINOR] F7:** L3 treats "committed" as "reviewed". A signer committed by the agent before setup (the guards are
  off before init) shows as `= kept`. Not stated in the threat model.

## Test-first evidence
- Every feat/fix/test commit has `Red:` and `Green:` lines.
- Both reviewers ran L1–L4 on their parents: each is red for the stated reason.
- **Gaps:**
  - the piped and unlisted-runner forms
  - a staged trust file
  - a rerun before committing
  - the secret-paths branch

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 37 | all ACs met; the "writes only in its repo" flag regressed (L2); F2 |
| Security | 25 | 17 | 2 MEDIUM (staged trust file; L2 regression), 4 LOW |
| Test quality & test-first | 20 | 18 | red on the parent verified; the gaps above |
| Plan conformance | 10 | 9 | L2's residual list is incomplete |
| Maintainability | 5 | 4 | `_agent_blocked` duplicates `guard-files.sh`; `unreviewed()` is computed twice |
| **Total** | 100 | **85** | **PASS** |

### Open for the human
- **MEDIUM:**
  - a staged trust file riding along with the commit step
  - the L2 regression (piped and unlisted-runner forms)
- **MINOR-to-MEDIUM:** F2, the rerun misreport and the missing commit step.
- **LOW and MINOR:**
  - `{cd,…}` and `unset CLAUDE_PROJECT_DIR`
  - unescaped review diffs
  - the CODEOWNERS later rule
  - the `getpwuid` `KeyError`
  - the non-UTF-8 review crash
  - the secret-paths test
  - the docs for `!` rows
  - the "committed = reviewed" residual
