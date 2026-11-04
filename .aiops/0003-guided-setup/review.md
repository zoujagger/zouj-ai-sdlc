---
id: 0003
verdict: PASS
commit: a5994bcea1a1f58b1859f1efb8636d1504beb69b
score: 86/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 9

<!-- State 5 PRE-REVIEW, round 9 (after M1–M5), the last round the human agreed to. Compiled only from the three
     fresh-context persona reports (base main @ 429614a, head a5994bc). Rounds 1–8 (76, 80, 78, 84, 89, 90, 85, 85)
     are in git history. The reviewers were told that guard text-parsing gaps are documented residual. The human
     decides what happens next. -->

## Summary
- **Verifier:** VERIFIED. 15/15 ACs. The M1–M5 proof tests are red on their parents for the stated reasons.
- **Code reviewer:** every AC met, no BLOCKER or HIGH. 2 MEDIUM, 2 MINOR, 3 LOW.
- **Security reviewer:** PASS, 20/25. 2 MEDIUM, 1 LOW.
- **Checks:** `make check` (172 tests), `make build` and `claude plugin validate .` pass.
- **CLI write scope (security reviewer):** under the agent, setup and `init --force` change no human-owned or
  protected file, and nothing is written outside the session's repo.

Verdict: **PASS, 86/100** by the rule. Four MEDIUMs are open, all about what reaches the human's adoption commit.
Two of them come from round-8 fixes:
- **[MEDIUM] M3 regression: a downgraded `config.json` planted before `init` is no longer flagged.**
  - `_as_setup_writes` accepts the template plus *any* profile's keys, so an untracked solo config passes as setup's
    own. It shows as `= kept` and goes into the commit step (labelled "profile solo").
  - The parent 674504d flagged it.
  - After the human's merge, the base ref's config is solo, which CI reads.
- **[MEDIUM] M1's review shows the disk copy, not the staged blob.**
  - For a key staged with git plumbing, the review section prints "(same as the template)", so the staged key is
    never shown.
  - Nothing tells the human to unstage it, so a later plain `git commit` takes it.
  - TROUBLESHOOTING's "read the diff it shows" is inaccurate for this case.
- **[MEDIUM] A staged key marked `--skip-worktree`/`--assume-unchanged` isn't flagged.**
  - Git then reports the disk as equal to the index.
  - The printed commit step fails (`git add` refuses a skip-worktree path), which nudges the human toward a plain
    `git commit` that takes the key.
- **[MEDIUM] Repo-local git filters or hooks planted before `init`** (`.git/config` `clean` filter,
  `.git/info/attributes`, `.git/hooks/pre-commit`) make the human's commit step commit content setup never showed.
  The file on disk stays the template, so there is no trace.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:114`; under a real tty by hand |
| AC-2 | ✅ met | `tests/test_setup.py:190` |
| AC-3 | ✅ met | `tests/test_setup.py:218` |
| AC-4 | ✅ met | `tests/test_setup.py:244`, `:257`, `:277`, `:294`; sha256 unchanged under the agent |
| AC-5 | ✅ met | `tests/test_setup.py:383`, `:309` (parsed-equality reading, plan.md) |
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
- **[MEDIUM] A planted downgraded config passes as setup's own** (`setup.py:219-236`).
  - Fix: accept the bare template always. Accept template plus profile keys only for the profile of a *human* run.
    Otherwise flag it `!`.
- **[MEDIUM] The staged blob isn't shown** (`setup.py:379-385`).
  - Fix: when content is staged but not on disk, print `git diff --cached HEAD -- <rel>` through `shown`, and add a
    `git restore --staged -- <rel>` step.
- **[MEDIUM] skip-worktree / assume-unchanged** (`setup.py:248-250`, `:215-216`).
  - Fix: compare blob ids (`git rev-parse :rel`, `HEAD:rel`, `git hash-object --no-filters rel`), and flag any
    scaffold path that has those bits (`git ls-files -v`).
  - Clear the bits in the printed step.
- **[MEDIUM] Repo-local filters and hooks**
  - Fix: stop setup's preflight with ✗ on repo-local filter, attributes, hooksPath or fsmonitor keys,
    `.git/info/attributes` and non-sample hooks, as `approve`/doctor already refuse.
  - Print the commit with hooks off.
  - Or document "check what the commit holds" in the threat model.
- **[LOW]** The commit step commits what is on disk later, not what setup checked (time-of-check to time-of-use).

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes** |
| Setup writing `.claude/settings.json` | **yes** (never written under the agent; only the pinned keys) |
| Profile changes through setup | **partly**: the agent can't change an existing config, but a planted solo config is no longer surfaced (MEDIUM) |
| `gh auth status` / `claude --version` | **yes** |
| No sandbox; setup writes only in its repo | **yes** at the CLI level (guard text parsing: documented residual) |
| `sdlc feedback` | **yes** |
| Unreviewed trust file stays out of setup's commit | **partly**: holds for plain planted and staged files; not for skip-worktree, repo-local filters/hooks, or a planted profile config (MEDIUMs) |

## Plan conformance
- S1–S15 are ticked, and M1–M5 are logged and match their commits.
- **Inaccurate:**
  - M3 says "setup's own files from an earlier run aren't flagged", but merged files are still flagged on a rerun.
  - M5's new known issues sit under the "Review round 2 (low)" heading.

## Other findings (code reviewer)
- **[MINOR]** A merged `settings.json` or `config.json` from a human run is flagged on the next rerun, with a wrong note
  ("not in any commit yet"; the file is in HEAD).
- **[MINOR]** M5's known issues are under the wrong CHANGELOG heading.
- **[LOW]** The commit step sweeps in uncommitted local edits to `Makefile`, `CLAUDE.md` or `.gitignore`.
- **[LOW]** M2's accepted false positive (a line mentioning `sdlc setup` next to `cd`, `-C3`, or a commit message) isn't
  in the CHANGELOG's false-positive list or TROUBLESHOOTING.
- **[LOW]** The inventory prints the stored profile unescaped, and bidi overrides pass `shown`.

## Test-first evidence
- Every commit has `Red:` and `Green:` lines.
- M1–M5 are red on their parents (verifier and code reviewer).
- **Gaps:**
  - a staged key where the disk equals the template (the review content)
  - a planted profile config
  - skip-worktree
  - a rerun after a merge
  - the secret-paths branch (known issue)

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 37 | all ACs met; the M3 regression; the staged-key review shows the wrong content |
| Security | 25 | 18 | 4 MEDIUM on the adoption commit, 1 LOW; no CLI write-scope finding |
| Test quality & test-first | 20 | 18 | red on the parent verified; the gaps above |
| Plan conformance | 10 | 9 | M3 claim overstated; CHANGELOG heading |
| Maintainability | 5 | 4 | `unreviewed()` computed twice |
| **Total** | 100 | **86** | **PASS** |
