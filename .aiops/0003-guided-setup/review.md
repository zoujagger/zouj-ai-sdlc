---
id: 0003
verdict: PASS
commit: 60ed7a0e9aa524ba54586fc363ba8a1d5dd0b6c9
score: 86/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 11

<!-- State 5 PRE-REVIEW. Round 11 is the pinning check after N1 and N2 (docs only since round 9, a5994bc). Compiled
     only from the three fresh-context persona reports (base main @ 429614a, head 60ed7a0). Rounds 1–10 are in git
     history. The human decided to ship at this commit. -->

## Summary
- **Verifier:** VERIFIED. Only docs, the docs test and `.aiops/` changed since round 9 (nothing under `lib/`, `bin/`,
  `hooks/`, `templates/` or `defaults/`). `make check` (172 tests), `make build` and `sdlc validate 0003` pass. N2's
  proof test is red on its parent.
- **Code reviewer:** no BLOCKER or HIGH. The corrected workaround's commands do what they say (a planted textconv and
  pager no longer hide a key from `git --no-pager log --stat --patch --no-textconv --no-ext-diff`). 1 MAJOR and several
  MINOR, all docs.
- **Security reviewer:** PASS, 18/25 (unchanged; the code is unchanged since round 9). The text no longer overclaims:
  textconv, pager, pre-commit and pre-push are caught by steps 1, 3 and 4. 2 LOW.

Verdict: **PASS, 86/100.** The four round-9 MEDIUMs on the adoption commit stay open in code, documented as alpha.3
known issues with the workaround. The human chose to ship at this commit with these docs gaps listed in the PR:
- **The workaround's step 2 is a wrong command** (CHANGELOG.md:133, TROUBLESHOOTING.md:91).
  `git update-index --no-skip-worktree --no-assume-unchanged -- <file>` in one call clears only assume-unchanged, so
  the skip-worktree bit stays and `git restore --staged` then fails. It fails closed: steps 3 and 4 still show the
  key. The correct form is two calls, `--no-skip-worktree` and then `--no-assume-unchanged`.
- **Steps 1 and 3 can still be blinded** by routes step 1 doesn't list:
  - `include.path` / `includeIf` (`git config --local --list` doesn't follow includes; `--includes --show-origin`
    does), and worktree config
  - `git replace` objects
  - a `-diff` attribute (also through `core.attributesFile`)
  - `log.showSignature` with `gpg.program` (runs a program during the step-3 read)
  - `color.*` (black on black)
  - a locally moved `origin/main`

  Step 4, the PR's "Files changed" on GitHub, read by a second person, is the authority, and the docs say so.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:114` (and the round-9 tty check) |
| AC-2 | ✅ met | `tests/test_setup.py:190` |
| AC-3 | ✅ met | `tests/test_setup.py:218` |
| AC-4 | ✅ met | `tests/test_setup.py:244`, `:257`, `:277`, `:294` |
| AC-5 | ✅ met | `tests/test_setup.py:383`, `:309` |
| AC-6 | ✅ met | `tests/test_setup.py:128` |
| AC-7 | ✅ met | `tests/test_engine.py:530`, `:500`, `:513`, `:392` |
| AC-8 | ✅ met | `tests/test_playbook.py:135-141` (approves through `approvals.approve`: known issue) |
| AC-9 | ✅ met | `tests/test_cli.py:96` |
| AC-10 | ✅ met | `tests/test_setup.py:765`, `:777` |
| AC-11 | ✅ met | `tests/test_setup.py:80` |
| AC-12 | ✅ met | `tests/test_shell_hooks.py` `test_onboarding_docs` |
| AC-13 | ✅ met | `tests/test_setup.py:791` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:349`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:190`, `tests/test_setup.py:190` (solo `!` by hand: known issue) |

## Security
- **Open in code, documented (round 9):** a planted profile config passes as setup's own; the review shows the disk
  copy instead of a staged blob; skip-worktree/assume-unchanged hide a staged key; repo-local filters/hooks planted
  before `init` change what is committed.
- **[LOW] Step 2 of the workaround doesn't clear skip-worktree** (two calls needed).
- **[LOW] Steps 1 and 3 have further local bypasses** (listed above); step 4 is the backstop.

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes** |
| Setup writing `.claude/settings.json` | **yes** |
| Profile changes through setup | **partly**: a planted solo config isn't flagged (documented) |
| `gh auth status` / `claude --version` | **yes** |
| No sandbox; setup writes only in its repo | **yes** at the CLI level (guard text parsing: documented residual) |
| `sdlc feedback` | **yes** |
| Adoption-commit integrity | **documented, not fixed**: steps 1–3 best-effort, step 4 (GitHub "Files changed") the authority |

## Plan conformance
- S1–S15 are ticked. Every fix round and human decision is logged.
- **Inaccurate:** the N2 row says the false-positive note "lists every relocation form" (`popd` and `-okdir` are
  missing) and that the test "asserts the exact commands" (it asserts key fragments). Both are recorded in the
  decision row after it.

## Test-first evidence
- Every code commit has `Red:` and `Green:` lines, and the fix rounds' proof tests are red on their parents.
- The docs test pins key fragments only; whether the documented commands behave as described is checked by the
  reviewers running them, not by the suite.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 37 | all ACs met; round-9 adoption-commit gaps documented |
| Security | 25 | 18 | four round-9 MEDIUMs open and documented; 2 LOW docs gaps |
| Test quality & test-first | 20 | 18 | red on the parent verified; the docs test asserts fragments |
| Plan conformance | 10 | 9 | N2 wording overstated (recorded) |
| Maintainability | 5 | 4 | `unreviewed()` computed twice |
| **Total** | 100 | **86** | **PASS** |
