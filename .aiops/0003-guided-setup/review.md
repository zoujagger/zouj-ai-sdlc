---
id: 0003
verdict: PASS
commit: a61904182a8ef3da91b8c73729092217ed7614ec
score: 90/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 6

<!-- State 5 PRE-REVIEW, round 6 (after J1–J6). Compiled only from the three fresh-context persona reports (base main
     @ 429614a, head a619041). Rounds 1–5 (76, 80, 78, 84, 89) are in git history. The human decides what happens
     next. -->

## Summary
Every AC is met, and no reviewer found a BLOCKER, CRITICAL or HIGH. The score is 90.
- **Verifier:** VERIFIED. 15/15 ACs. The J2–J6 proof tests are red on their parents, and J1's mutation check
  catches a broken engine.
- **Code reviewer:** no BLOCKER, HIGH or MAJOR; 2 LOW and 3 MINOR. All ACs ✅; AC-8 is no longer partial.
- **Security reviewer:** PASS, 19/25; 2 MEDIUM and 1 LOW.
- **Checks:** `make check` (158 tests), `make build` and `claude plugin validate .` pass, and so does
  `sdlc validate 0003`. The 2 validator warnings are unrelated: a root CLAUDE.md that isn't loaded, and no icon.

Verdict: **PASS, 90/100.** These findings stay open for the human's merge decision:
- **[MEDIUM] Agent `init --force` resets protected paths the guard won't let it write.**
  - Under the agent, `--force` keeps only the hard-coded human-owned list (`HUMAN_OWNED_RE`). It ignores the default
    and repo `protected-paths` (`governance/*`, a repo-protected `Makefile`) and the read-only lock.
  - The reviewer reset a wired, protected Makefile to the stub recipes, after which `make check` passed trivially.
  - The content is the fixed scaffold, and the reset shows in the PR diff.
- **[MEDIUM] The J3 root check can be redirected.**
  - `GIT_DIR`/`GIT_WORK_TREE`, `git init <ancestor>`, or a `cd` into another of the user's repos lets the agent
    scaffold another directory or repo: its `.claude/settings.json`, or a parent `CLAUDE.md` that loads in every child
    project. The guard blocks a direct write to those files.
  - `$HOME`, `~/.claude` and toolchain paths stay refused, and the content is the fixed scaffold.
  - The code reviewer rated the same route LOW.
- **Open question on `strict`, not verified here.** The security reviewer saw OpenSSH 10.2 reject `no-touch-required`
  in `allowed_signers` as an unknown option (it is an `authorized_keys` option). If so, that option never appears in
  a valid signers file. Strict's "a touch per signature" then rests on whether `ssh-keygen -Y verify` checks the
  user-presence flag of `sk-` signatures, which needs a FIDO device to test.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:110`, `:20`; own runs (0.35–1.2 s) |
| AC-2 | ✅ met | `tests/test_setup.py:186`; the README recipe run end to end ("No intents yet"; read-only proven through the pre-edit hook) |
| AC-3 | ✅ met | `tests/test_setup.py:214` |
| AC-4 | ✅ met | `tests/test_setup.py:240`, `:253`, `:273`; hashes unchanged under the agent |
| AC-5 | ✅ met | `tests/test_setup.py:362`, `:288` (values compared as parsed JSON, the plan's interpretation) |
| AC-6 | ✅ met | `tests/test_setup.py:124` |
| AC-7 | ✅ met | `tests/test_engine.py:530`, `:513` (any letter case), `:392` (CI audit and doctor ✗) |
| AC-8 | ✅ met | `tests/test_playbook.py:115-141`: a CHANGES_REQUESTED review stays at state 5 on the branch and on main, in each profile; only PASS reaches 6 |
| AC-9 | ✅ met | `tests/test_cli.py:59` |
| AC-10 | ✅ met | `tests/test_setup.py:564`, `:576` |
| AC-11 | ✅ met | `tests/test_setup.py:76`, `:492` (tools planted in the repo aren't run) |
| AC-12 | ✅ met | `tests/test_shell_hooks.py:304`, `:255` |
| AC-13 | ✅ met | `tests/test_setup.py:590` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:336`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:153`, `tests/test_setup.py:209` (solo `!` checked by hand, not in a test) |

## Security
- **[MEDIUM] Agent `init --force` vs protected paths** (`lib/sdlc_engine/cli.py:304` `HUMAN_OWNED_RE`,
  `init_actions`).
  - Fix: under the agent, keep any existing scaffold file that matches the default or repo `protected-paths`, or that
    the lock forbids. Or refuse `init --force` under the agent and print the command for the human. Add tests for
    `governance/` and for a repo-protected path.
- **[MEDIUM] Root redirection** (`cli.py:307` `scaffold_root_problem`, `machine.project_root`, `machine.git`).
  - Fix: run the root lookup with `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`, `GIT_INDEX_FILE` and
    `GIT_CEILING_DIRECTORIES` removed, and refuse when they are set.
  - Under the agent, require the root to equal the session's project (`CLAUDE_PROJECT_DIR`'s top level).
  - Name what remains in the threat model.
- **[LOW] Quoted option values fool doctor's strict allow-list check** (`approvals.py:365` `signer_entries`).
  - Example: `namespaces="git, sk-ssh-ed25519@openssh.com <blob> x" ssh-ed25519 <key>` is accepted by OpenSSH,
    yet doctor shows strict ✓.
  - CI fails safe: there is no fingerprint match, so the signer is refused.
  - Fix: parse options with OpenSSH quoting, and treat unparseable lines as non-touch.
- **Residual, documented:** an interpreter that strips the env markers runs setup "as the human" locally. CI reads
  the base ref (`skills/setup/SKILL.md`, `docs/architecture.md`).

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes**, stated |
| Setup writing `.claude/settings.json` | **yes in the repo** (only the pinned marketplace keys; untouched under the agent); **not in another repo** reached by the root redirection (MEDIUM) |
| Profile changes through setup | **yes**, within the documented env-marker residual |
| `gh auth status` / `claude --version` | **yes** (in-repo PATH skipped, stdin closed) |
| No sandbox; setup writes only in its repo | **partially**: symlinks, `$HOME`, `~/.claude` and toolchain roots are refused, but the root can be redirected, and agent `--force` resets protected paths (MEDIUMs) |
| `sdlc feedback` | **yes** |

## Plan conformance
- S1–S15 are ticked and each maps to a commit.
- The fix rounds (F1–F6, G1–G2, H1–H4, J1–J6) and every human decision are in the Deviation log. J1–J6 were checked
  against their diffs.
- **Partly overstated:**
  - J3 says it "closes the fallback to the current directory", but `GIT_DIR` reopens it.
  - J4 says "write errors are reported", but a non-UTF-8 `.gitignore` still ends in a traceback.
- **Docs:**
  - A stale CHANGELOG known issue (the FAIL-review test exists now).
  - The "PATH" known issue predates J4.
  - TROUBLESHOOTING's "(and `init`)" covers more stop reasons than `init` checks.

## Test-first evidence
- Every J commit has `Red:` and `Green:` lines. Both reviewers ran each fix's proof tests on its parent:
  - J2: 2 failures
  - J3: 3 of 4 (the subdirectory test is a regression guard)
  - J4: 7 failures and 1 error
  - J5: 2 failures
  - J6: 2 failures
- J1 is a logged pin; its mutation check fails all three profiles (`6 != 5`).
- **Gaps:**
  - a `GIT_DIR`-redirected root
  - a non-UTF-8 `.gitignore`
  - the human-step wording when a config already existed
  - AC-15's solo `!` row
  - the playbook test drives `approvals.approve`, not the prompt hook

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 39 | all ACs met; the "writes only in its repo" flag is still bypassable |
| Security | 25 | 19 | 2 MEDIUM, 1 LOW; no CRITICAL or HIGH |
| Test quality & test-first | 20 | 19 | red on the parent confirmed for J2–J6; J1's mutation check; the gaps above |
| Plan conformance | 10 | 9 | J3/J4 claims slightly overstated; stale docs lines |
| Maintainability | 5 | 4 | `setup.main` is long; one decode error still ends in a traceback |
| **Total** | 100 | **90** | **PASS** |

### Open for the human (fix before merge, or alpha.3 known issues)
- **MEDIUM:**
  - agent `init --force` vs protected paths and the lock
  - the root redirection
- **The `strict` open question:** does `ssh-keygen -Y verify` enforce the touch, given that `no-touch-required`
  isn't valid in `allowed_signers`?
- **LOW:**
  - doctor's quoted-option parse
  - a non-UTF-8 `.gitignore` traceback
  - strict's signing help suggests a passphrase key (doctor, `approve`)
- **MINOR:**
  - the human-step wording when a config already existed
  - the stale and outdated CHANGELOG known issues
  - TROUBLESHOOTING's "(and `init`)"
- **Already listed as known issues:**
  - an agent run prints the current profile's signing steps
  - "Already set up" prints no Doctor section
