---
id: 0007
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: c6da1ebf64777fdd36c32ad9f271d552b5d8c5d5
score: 90/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-16
---

# Review: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Rounds 1-3 reviewed the removed `Setup Profile` phrase (PASS 86, 88, 92). Round 4 (a693a2f): CHANGES_REQUESTED 89.
     Round 5 (53c90c0): CHANGES_REQUESTED 87. Round 6: fixed in e704354. Round 7: PASS 92, its LOWs and NITs fixed
     in f38003b. Round 8 (f38003b): CHANGES_REQUESTED 92, fixed
     in 93e86fe. Round 9 (93e86fe): CHANGES_REQUESTED 88, fixed
     in 5dc89c5. Round 10 (5dc89c5): CHANGES_REQUESTED 86, fixed
     in 6b25573. Round 11 (6b25573): CHANGES_REQUESTED 92, fixed
     in dd4c768. Round 12 (dd4c768): CHANGES_REQUESTED 89, fixed
     in 4b72255. Round 13 (4b72255): CHANGES_REQUESTED 86, fixed
     in 70dfd3d. Round 14 (70dfd3d): CHANGES_REQUESTED 88, fixed
     in 9b068a1. Round 15 (9b068a1): CHANGES_REQUESTED 91, fixed in 2ef6811; round 16 stopped by the human, who
     merged PR #19. Final round on main at c6da1eb (this file), diff against 6fe9808 (main before 0007). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It merged in PR #18 (rounds 1-3) and PR #19 (rounds 4-15), and ships as the next release (0.2.0-beta.1, a separate
change).

Final round, on main at `c6da1eb` against `6fe9808`:
- **Verifier:** VERIFIED. All 23 ACs proven. `make check` (442), `make build` and `sdlc validate 0007` pass.
- **Code-reviewer:** PASS leaning, ~90/100, no BLOCKER, five MINOR (one with security impact LOW).
- **Security-reviewer:** PASS, 23/25, no CRITICAL or HIGH; the accepted MEDIUM and one new LOW.

**Verdict: PASS.** Total 90, no BLOCKER or CRITICAL/HIGH, every AC met. The items below go to the backlog.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:1390`; `tests/test_cli.py:532` |
| AC-2 | ✅ met | `tests/test_playbook.py:344 CommandWalk` (drives `hooks/engine.sh` only, both markers) |
| AC-3 | ✅ met | `tests/test_setup.py:1437`, `:1442`, `:1453`, `:1464`; `tests/test_cli.py:579`; `test_worktree_redirect_is_refused` |
| AC-4 | ✅ met | `tests/test_cli.py:548`, `:565` |
| AC-5 | ✅ met | `tests/test_shell_hooks.py:691` |
| AC-6 | ✅ met | `tests/test_cli.py:618` |
| AC-7 | ✅ met | `tests/test_cli.py:640` |
| AC-8 | ✅ met | `tests/test_setup.py:1341`, `:1578`, `:1585`, `:1604` |
| AC-9 | ✅ met | `tests/test_cli.py:694` |
| AC-10 | ✅ met | `tests/test_cli.py:741`, `:758`, `:767`, `:798` |
| AC-11 | ✅ met | `tests/test_cli.py:413`; `tests/test_setup.py:973` |
| AC-12 | ✅ met | `tests/test_cli.py:422`, `:432`, `:437`, `:448`; `tests/test_setup.py:1008` |
| AC-13 | ✅ met | `tests/test_lifecycle.py:770`, `:782` |
| AC-14 | ✅ met | `tests/test_lifecycle.py:716`; `tests/test_cli.py:455`, `:462` |
| AC-15 | ✅ met | `tests/test_lifecycle.py:837`, `:847`, `:854` |
| AC-16 | ✅ met | `tests/test_playbook.py:338 CoreWalk`, `:344 CommandWalk` × solo/team/strict |
| AC-17 | ✅ met | `tests/test_cli.py:821`; no `defaultMode` in the scaffold settings |
| AC-18 | ✅ met (amended AC) | `tests/test_setup.py:895`; `tests/test_cli.py:833`, `:850`, `:866`, `:877`, `:1009` |
| AC-19 | ✅ met | `plugin.json` `0.2.0-alpha.4`; `tests/test_cli.py:925`; `tests/test_rules.py:326`; `make build` passes |
| AC-20 | ✅ met | `tests/test_cli.py:471`, `:486` |
| AC-21 | ✅ met (run quoted below) | `tests/test_cli.py:955`; `evals/README.md:22` |
| AC-22 | ✅ met | `tests/test_setup.py:1077`, `:1184` |
| AC-23 | ✅ met | `tests/test_setup.py:1196`, plus the below-the-top and repo-config refusals |

**AC-21: the run** (plan.md Deviation log S19, 2026-11-13; `--allow-tools Bash Write Edit`, 3 runs per arm):
`profile-by-setup-command` 1.00 with the plugin (asks-for-setup-command PASS ×3, config-unchanged ✓ ×3), 0.67
without, Δ +0.33, $0.87. Since that run (`ae31453`) `evals/` and `skills/setup` are unchanged; the verifier could not re-run it (tool scope).

## Security
- [MEDIUM, accepted residual] An agent-started session (`claude -p "/zouj-ai-sdlc:setup solo"`) can type the command.
  Bounded to the session's repo with the untouched template config and nothing approved in its files or history;
  one visible commit; CI reads the base config. Recorded in Known gaps with the planned pre-bash rule.
- [LOW] `setup.py:755-760` `_differs` (and `_as_setup_writes`) reads a planted FIFO at a scaffold path
  (`mkfifo Makefile` while the gates are dormant), so the typed command hangs until the hook times out.
  Availability only; typing it again succeeds. → Backlog.
- [LOW, code-reviewer] `sdlc setup|init --with <part>` run by the agent creates the part's missing files in any state,
  including code under the lock (`scripts/check-bands.py`) and protected workflows, unlike `upgrade`/`repair`
  (`agent_may_write`). Plugin templates only; CODEOWNERS reviews `/.github/`. → Backlog.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | `no_profile_yet`, `approval_in_history`, template + `PROFILE_CONFIG`, `_commit_alone(data=)` |
| The hook writes the core scaffold without a preview (R-2a) | Yes | `scaffold_first` create-only, `write_file` O_NOFOLLOW/O_EXCL, top of the work tree; created and differing kept files listed |
| The agent prompts a session of its own | Partly (accepted) | MEDIUM above |
| The agent asks the human to type the command | Yes | a bare command previews; `systemMessage` built apart and escaped |
| The profile commit is unsigned in team/strict | Yes (by design) | opens no gate; CI reads the base config; one-line `approver()` |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | preview and `list-installed` name the parts left out |
| No change to secrets, lock, approval path, audit, allowed-commands | Yes | `approve()` unchanged apart from sharing `_commit_alone` |

## Plan conformance
- **Steps:** S1-S20 are done and match the diff; every divergence, S1-S20 and rounds r1-r15, is in the Deviation log.
- **Gap:** the agent's `--with` under the lock (Security above) is outside the spec's threat analysis.
- **Open:** a manual `make dev` session typing the command (the r4 `claude -p` probe covers the hook path).

## Test-first evidence
Every step S1-S20 and fix round r1-r15 has a `Red:` line naming its failing tests; S17 says its red came from S14
and S16. Tests and code share commits, as REVIEW.md accepts.

## Backlog (not blocking)
- The FIFO hang (LOW) and the agent's `--with` under the lock (LOW): `agent_may_write` for `setup|init --with`.
- `sdlc init` reads only the first `--with`; `setup` merges them. → One parser.
- Freeze `_plugin_engine_sh`; further G-GATE-07 hardening goes to intent 0006 with a must-block/must-allow matrix.
- `KeptList`/`Reply` carry data on built-in subclasses. → Named tuples.
- TROUBLESHOOTING: a repo-local `core.hooksPath` (husky, lefthook) makes the typed command refuse.
- `tests/test_guards.py:2079-2191` `"\;"` SyntaxWarnings (from 0005).
- Re-run `evals/profile-by-setup-command` at the release commit (the quoted run predates small edits to
  `skills/configure` and `hooks/engine.sh`).

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | Every AC met; the agent's `--with` under the lock is outside the threat analysis |
| Security | 25 | 22 | The accepted MEDIUM; two LOWs |
| Test quality & test-first | 20 | 18 | Real-outcome tests; red runs recorded in text |
| Plan conformance | 10 | 9 | One unanalysed behaviour |
| Maintainability | 5 | 3 | The guard's heuristics; side data on built-in subclasses |
| **Total** | 100 | **90** | PASS: ≥ 80, no BLOCKER or HIGH, every AC met |
