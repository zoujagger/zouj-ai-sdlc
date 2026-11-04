---
id: 0003
verdict: PASS
commit: b2ef347ef4b0097bc40361f219a2d5c799e531a4
score: 85/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-04
---

# Review: Guided setup and first-run onboarding (roadmap phase 1), round 7

<!-- State 5 PRE-REVIEW, round 7 (after K1–K3). Compiled only from the three fresh-context persona reports (base main
     @ 429614a, head b2ef347). Rounds 1–6 (76, 80, 78, 84, 89, 90) are in git history. The human decides what
     happens next. -->

## Summary
- **Verifier:** VERIFIED. 15/15 ACs. The K1–K3 proof tests are red on their parents.
- **Code reviewer:** every AC met, no BLOCKER or HIGH. 1 MEDIUM, 1 LOW, 2 MINOR.
- **Security reviewer:** PASS, 20/25. 2 MEDIUM, 2 LOW.
- **Checks:** `make check` (161 tests) and `make build` pass.

Verdict: **PASS, 85/100.** By the rule: no BLOCKER, CRITICAL or HIGH, every AC ✅, and a score of 80 or more. Three
MEDIUMs are open, and one of them means **K1's fix and its description are wrong**:
- **[MEDIUM] K1 doesn't cover protected paths.**
  - `_agent_blocked` asks `guards.check_edit`, but `check_edit` checks only the plugin dir, engine paths, artifacts
    and the read-only lock. Protected paths are enforced by `hooks/guard-files.sh`, a separate hook (confirmed while
    compiling this review).
  - So in state 4, or with `lock_when_idle: false`, agent `init --force` still resets a protected Makefile or
    `governance/*`.
  - K1's proof test passes only through the lock.
  - The K1 Deviation-log entry, the CHANGELOG ("protected paths, the read-only lock") and the `docs/architecture.md`
    row overstate the fix.
- **[MEDIUM] K2 is bypassed by `CLAUDE_PROJECT_DIR=` in the command.**
  - `machine.project_root` prefers that variable, and the guard compares only the hook's own copy.
  - So `CLAUDE_PROJECT_DIR=<other repo> sdlc init` (or `export …;`) scaffolds another repo.
  - `env --chdir`, an attached `-C<dir>` and `find -execdir` also get past the guard's text match (code reviewer:
    LOW).
- **[MEDIUM] A signer planted before setup can reach main.**
  - In a repo that isn't initialized yet, the guards are off, so the agent can write `.aiops/config/allowed-signers`
    with its own key, or an empty `protected-paths`.
  - Setup then shows it only as `= … (kept)` among about 35 `+` rows, and the human steps say
    `git add -A && git commit`.
  - Once that merges, CI trusts the agent's key. This attacks the human step the hard guarantee rests on.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:110`, `:20`; under a real tty by hand |
| AC-2 | ✅ met | `tests/test_setup.py:186` |
| AC-3 | ✅ met | `tests/test_setup.py:214` |
| AC-4 | ✅ met | `tests/test_setup.py:240`, `:253`, `:273`; sha1 unchanged under the agent |
| AC-5 | ✅ met | `tests/test_setup.py:362`, `:288` (parsed-equality reading, plan.md:40) |
| AC-6 | ✅ met | `tests/test_setup.py:124` |
| AC-7 | ✅ met | `tests/test_engine.py:530`, `:513` (no end-to-end `approve` under "sk", no real FIDO key: known issues) |
| AC-8 | ✅ met | `tests/test_playbook.py:135-141` (approves through `approvals.approve`: known issue) |
| AC-9 | ✅ met | `tests/test_cli.py:77` |
| AC-10 | ✅ met | `tests/test_setup.py:596`, `:608` |
| AC-11 | ✅ met | `tests/test_setup.py:76` |
| AC-12 | ✅ met | `tests/test_shell_hooks.py:308`, `:255` |
| AC-13 | ✅ met | `tests/test_setup.py:622` |
| AC-14 | ✅ met | `tests/test_shell_hooks.py:340`; `make build` |
| AC-15 | ✅ met | `tests/test_cli.py:171` (solo `!` by hand: known issue) |

## Security
- **[MEDIUM] Agent `init --force` vs protected paths when unlocked** (`lib/sdlc_engine/cli.py:363-367`).
  - Fix: also keep a file when `glob_hit(rel, globs(root, "protected-paths"))` hits, or when the `.aiops` checks
    hit, as `guards.py:707-711` does. Add an unlocked case to the test (`lock_when_idle: false`).
  - Correct the K1 claims.
- **[MEDIUM] `CLAUDE_PROJECT_DIR=` redirects the agent's init/setup** (`guards.py:374-388`, `machine.py:49`,
  `cli.py:715`).
  - Fix: for `init`/`setup`, take the root from the working directory's git top level only. Refuse when
    `CLAUDE_PROJECT_DIR` is set and differs.
  - Extend `RELOCATE_RE` to `CLAUDE_PROJECT_DIR=`, `HOME=`, `--chdir`, an attached `-C…` and `-execdir`/`-okdir`.
  - List the residual forms in the threat model.
- **[MEDIUM] A pre-planted `allowed-signers` or `protected-paths` is kept silently, then `git add -A`**
  (`setup.py:212-213`, `:417`, `:181`).
  - Fix: show any existing human-owned file as `!` with its content or its diff against the template. On a repo that
    isn't initialized yet, require an explicit confirmation for it.
  - List the allowed-signers entries.
  - Commit the explicit scaffold paths, not `git add -A`.
- **[LOW] `$HOME` is trusted for the home and `~/.claude` refusals** (`cli.py:322-325`).
  - Fix: also check `pwd.getpwuid(os.getuid()).pw_dir`.
- **[LOW] The agent's profile human step repeats a downgrade the agent asked for.**
  - The human still confirms a diff.
  - Fix: label a weaker profile "downgrade requested by the agent's run".

Spec flags:

| Flag | Mitigated? |
|---|---|
| Solo approvals are unsigned | **yes**, stated |
| Setup writing `.claude/settings.json` | **yes in the session repo** (sha1 unchanged under the agent); another repo is reachable through `CLAUDE_PROJECT_DIR=` (MEDIUM) |
| Profile changes through setup | **yes**, within the documented env-marker residual |
| `gh auth status` / `claude --version` | **yes** |
| No sandbox; setup writes only in its repo | **partially** (`CLAUDE_PROJECT_DIR=`, `--chdir` and similar) |
| `sdlc feedback` | **yes** |

## Plan conformance
- S1–S15 are ticked, and K1–K3 are logged.
- **Inaccurate:**
  - The K1 entry says `check_edit` covers the default and repo protected-paths. It doesn't.
  - The K2 entry's residual list is incomplete.
- The K3 known issues match the code. The removed entries are really fixed.

## Test-first evidence
- All 36 step and fix commits have `Red:` and `Green:` lines.
- K1–K3 are red on their parents (both reviewers).
- **Gaps:**
  - K1's test passes on the lock alone. With `lock_when_idle: false` it fails (code reviewer's mutation).
  - K2's test misses `CLAUDE_PROJECT_DIR=`, `--chdir`, an attached `-C` and `-execdir`.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | all ACs met; the "writes only in its repo" and "human-owned" flags are still partly bypassable |
| Security | 25 | 17 | 3 MEDIUM (K1 when unlocked, `CLAUDE_PROJECT_DIR=`, a planted signer kept silently), 2 LOW; no HIGH |
| Test quality & test-first | 20 | 18 | red on the parent verified; K1's test misses its own case |
| Plan conformance | 10 | 8 | the K1 entry, the CHANGELOG and the architecture row overstate K1 |
| Maintainability | 5 | 4 | two implementations of "what the guard blocks" (`check_edit` vs `guard-files.sh`) |
| **Total** | 100 | **85** | **PASS** |

### Open for the human
- **MEDIUM:** K1 when unlocked (and its wrong claims), the `CLAUDE_PROJECT_DIR=` bypass, and a pre-planted signer
  kept silently.
- **LOW:** `$HOME` trust, the downgrade wording, and the `--chdir` / `-C<dir>` / `-execdir` forms.
- **MINOR:**
  - `GIT_CEILING_DIRECTORIES` is refused with a wrong reason (it only limits git's search).
  - The guard's whole-line text match blocks harmless commands that mention `sdlc setup` next to a `cd`.
  - The agent-run commit message names a profile the agent didn't apply.
