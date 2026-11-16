---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 70dfd3dc79e74724f5d4c6c8bb1c344d08d3426d
score: 88/100
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
     in 70dfd3d. Round 14 at 70dfd3d (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 14 results:
- **Verifier:** VERIFIED (AC-21's live run carried over). `make check` (441), `make build` and `sdlc validate 0007` pass.
- **Code-reviewer:** CHANGES_REQUESTED 88, **one MAJOR** (a false positive), two MINOR.
- **Security-reviewer:** PASS, 22/25, no CRITICAL, HIGH or MEDIUM, two LOW. The r13 MAJOR (shell options) is closed.

**Verdict: CHANGES_REQUESTED.** The r13 shell-word check refuses any word under `~/.claude/plugins/` or naming
`CLAUDE_PLUGIN_ROOT`, in every repo, so another plugin's `bash ~/.claude/plugins/cache/other/tool/scripts/build.sh`
or `bash -c "ls ~/.claude/plugins/cache"` is blocked as G-GATE-07 with the wrong reason. Installing this plugin
user-wide must not break other plugins.

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
Closed since round 13: shell options with a separate argument (`-O`, `+O`, `--rcfile`, `--init-file`, `-c`), a bare
name a shell reads from the cwd, the size check, escaped scaffold refusals.

Round 14 findings:
- [LOW] An inline `PATH=$PWD:$PATH run prompt`, with `run` a copy or link of the plugin's script, passes. Same class
  as "a copy under another name" in Known gaps. → Name it as an example.
- [LOW] `hook_profile` reads `CLAUDE_PROJECT_DIR` from its own environment, which a fed-payload form controls. →
  Known gaps: the session-repo condition holds for a hook Claude Code started.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Yes | session repo and `core.worktree` checks, `no_profile_yet`, `_commit_alone(data=)`, one-line `approver()` |
| The hook writes the core scaffold without a preview (R-2a) | Yes | missing files only, top of the work tree, quick Preflight; created and differing kept files listed |
| The agent prompts a session of its own | Accepted residual | literal fed forms refused (probed); the rest documented as a class |
| The agent asks the human to type the command | Yes | `PROOF` per profile; a bare command previews |
| The profile commit is unsigned in team/strict | Accepted | opens no gate; CI reads the base config |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | `parts=[]`; `list-installed` names the parts left out |

## Plan conformance
- **Steps:** all 20 are done; r13 is logged (`plan.md:334`).
- **Unintended:** the block on any `.claude/plugins/` word is a side effect, not a logged behaviour (MAJOR).
- **Open:** the manual `make dev` check; `pr.md`'s stale ADR link.

## Test-first evidence
Every step and review fix records its red run (S14-S20, r4-r13). Gap: no must-allow test for another plugin's
directory.

## Fixes requested
1. **[MAJOR] `lib/sdlc_engine/guards.py:381-390`**: a word in another plugin's directory is refused. → Count a
   shell argument as ours only when its name is `engine.sh` (resolved, failing closed), a glob or variable name
   that could expand to it, or a literal path resolving to the plugin's script or a byte-equal copy; must-allow
   tests for another plugin's script and `bash -c "ls ~/.claude/plugins/cache"`, red first.

## Other findings (non-blocking)
- [MINOR] `setup.py` `_differs` compares with the raw template, not what init writes (`__ZOUJ_SDLC_REF__` →
  `v<version>`): an `aiops-gates.yml` equal to init's output is flagged, a raw-placeholder copy isn't. → Compare
  with the rendered bytes.
- [MINOR] `ash`, `mksh` (and `csh`/`tcsh`/`yash`) aren't shells to the guard; a modified copy or a written script
  still passes (the documented class). → Add the shells.
- [LOW] the two Known gaps examples (Security above).
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 37 | Every AC met; the kept-files check compares the raw template |
| Security | 25 | 22 | No opening; LOW examples of the documented class |
| Test quality & test-first | 20 | 17 | No must-allow test for another plugin |
| Plan conformance | 10 | 9 | An unlogged side effect |
| Maintainability | 5 | 3 | Overlapping guard regexes |
| **Total** | 100 | **88** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the MAJOR (user-wide false positive) blocks |
