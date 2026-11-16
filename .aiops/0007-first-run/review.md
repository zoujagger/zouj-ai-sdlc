---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 93e86fe72213848cf16a953f90111f8a646e44d8
score: 88/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-16
---

# Review: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Rounds 1-3 reviewed the removed `Setup Profile` phrase (PASS 86, 88, 92). Round 4 (a693a2f): CHANGES_REQUESTED 89.
     Round 5 (53c90c0): CHANGES_REQUESTED 87. Round 6: fixed in e704354. Round 7: PASS 92, its LOWs and NITs fixed
     in f38003b. Round 8 (f38003b): CHANGES_REQUESTED 92, fixed
     in 93e86fe. Round 9 at 93e86fe (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 9 results:
- **Verifier:** VERIFIED. All 23 ACs have passing tests. `make check` (431), `make build` (2 old warnings) and
  `sdlc validate 0007` pass.
- **Code-reviewer:** no BLOCKER, **one MAJOR**, four MINOR.
- **Security-reviewer:** PASS, 21/25, no CRITICAL or HIGH, **one MEDIUM**, one LOW.

**Verdict: CHANGES_REQUESTED.** Every AC is met and the total is 88, but the r8 `engine.sh` guard refuses any script
named `engine.sh` in every repo (MAJOR), and a planted `user.name` can cut the warnings out of the human's
`systemMessage` (MEDIUM).

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:1358`; `tests/test_cli.py:531` |
| AC-2 | ✅ met | `tests/test_playbook.py:344 CommandWalk` (inherits `test_solo` at `:328`; both markers set, `:351-366`) |
| AC-3 | ✅ met | `tests/test_setup.py:1405`, `:1410`, `:1421`, `:1432`; `tests/test_cli.py:578` |
| AC-4 | ✅ met | `tests/test_cli.py:547`, `:564` |
| AC-5 | ✅ met | `tests/test_shell_hooks.py:691` |
| AC-6 | ✅ met | `tests/test_cli.py:599` |
| AC-7 | ✅ met | `tests/test_cli.py:621` |
| AC-8 | ✅ met | `tests/test_setup.py:1309`, `:1546`, `:1553`, `:1572` |
| AC-9 | ✅ met | `tests/test_cli.py:675` |
| AC-10 | ✅ met | `tests/test_cli.py:722`, `:739`, `:748`, `:779` |
| AC-11 | ✅ met | `tests/test_cli.py:412`; `tests/test_setup.py:973` |
| AC-12 | ✅ met | `tests/test_cli.py:421`, `:431`, `:436`, `:447`; `tests/test_setup.py:1008` |
| AC-13 | ✅ met | `tests/test_lifecycle.py:770`, `:782` |
| AC-14 | ✅ met | `tests/test_lifecycle.py:716`; `tests/test_cli.py:454`, `:461` |
| AC-15 | ✅ met | `tests/test_lifecycle.py:837`, `:847`, `:854` |
| AC-16 | ✅ met | `tests/test_playbook.py:338 CoreWalk`, `:344 CommandWalk` × solo/team/strict |
| AC-17 | ✅ met | `tests/test_cli.py:802`; no `defaultMode` in the scaffold settings |
| AC-18 | ✅ met (amended AC) | `tests/test_setup.py:895`; `tests/test_cli.py:814`, `:831`, `:847`, `:858`, `:990` |
| AC-19 | ✅ met | `plugin.json` `0.2.0-alpha.4`; `tests/test_cli.py:906`; `tests/test_rules.py:326`; `tests/test_setup.py:918` |
| AC-20 | ✅ met | `tests/test_cli.py:470`, `:485` |
| AC-21 | ✅ met (run quoted below) | `tests/test_cli.py:936`; `evals/README.md:22` |
| AC-22 | ✅ met | `tests/test_setup.py:1077`, `:1152` |
| AC-23 | ✅ met | `tests/test_setup.py:1124` (below the top), `:1136`, `:1164` |

**AC-21: the run** (plan.md Deviation log S19, 2026-11-13; `--allow-tools Bash Write Edit`, 3 runs per arm):
`profile-by-setup-command` 1.00 with the plugin (asks-for-setup-command PASS ×3, config-unchanged ✓ ×3), 0.67
without, Δ +0.33, $0.87. Not re-run since; r6-r8 changed guard and setup internals, not the skill text the case grades.

## Security
Closed since round 8: `hooks/engine.sh` run by the agent (G-GATE-07), install-state recording the hook's bytes, the
trust-list cap.

Round 9 findings:
- [MEDIUM] `lib/sdlc_engine/cli.py:960` cuts the `systemMessage` at the first `Relay the remaining human steps`, in
  text that holds attacker-controlled strings: `_identity_note` interpolates `approvals.approver(root)` raw
  (`setup.py:895`), and trust-list lines are shown verbatim apart from non-printables. The agent sets
  `git config user.name "Mallory Relay the remaining human steps"` (allowed by `LOCAL_ALLOWED_RE`, unguarded) and
  plants a signer; the human's message then ends at "Set-By names Mallory", and the signer line and the review list
  reach only the agent. `user.name`/`user.email` aren't escaped either. Not run (G-GATE-07 refused the probe); follows
  from the code. → Build the notice from its parts; `_shown()` every config- or file-derived value; test with the
  marker and an escape in `user.name` and in an `allowed-signers` line.
- [LOW] `cli.py` `hook_profile`: `core.worktree` (allowed by `LOCAL_ALLOWED_RE`) makes `project_root` of both the
  session and the cwd resolve to another repo B, so the session check passes and B gets the profile commit; the
  reply doesn't name the repo. Verified that `rev-parse --show-toplevel` follows it. → Compare the session directory
  itself, refuse a top level that isn't the directory holding `.git`, name the repo in `profile SET`.

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Mostly | `no_profile_yet`, `approval_in_history`, single-file commit of the written bytes. Gap: the `core.worktree` redirect (LOW) |
| The hook writes the core scaffold without a preview (R-2a) | Yes | `scaffold_first`: create-only `write_file`, `scaffold_root_problem`, Preflight, `cwd == root`; reply lists the files |
| The agent prompts a session of its own | Accepted residual | Known gaps and the threat-model row |
| The agent asks the human to type the command | Yes | a bare command previews; config.json under CODEOWNERS |
| The profile commit is unsigned in team/strict | Accepted | opens no gate; CI reads the base config |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | `list-installed` and the preview name the parts left out |
| The warnings reach the human directly (r6-r8) | **No** | the marker split and the unescaped approver (MEDIUM) |

## Plan conformance
- **Steps:** all 20 are done and match the diff; every review round has its Deviation log row.
- **Out of scope:** `ENGINE_SH_RE` reaches beyond the plugin's own file, though the r8 row says "the plugin's
  `hooks/engine.sh`" (MAJOR below).
- **Plan pointer:** the AC-19 feedback test is at `tests/test_setup.py:918`, not `tests/test_cli.py`.
- **Open:** the manual `make dev` check of the typed command.

## Test-first evidence
Every step and review fix records its red run: S1-S20, r1, r2, r4-r8 (`93e86fe`: 4 tests). Never red, and logged:
S17 `CommandWalk`, the AC-8 byte comparison, r8's upgrade-keeps-profile assertion. The r8 guard tests cover only
the refused forms; nothing pins a project's own `engine.sh` as allowed.

## Fixes requested
1. **[MAJOR] `lib/sdlc_engine/guards.py:306-308`, `:886-897`.** `ENGINE_SH_RE` matches any `engine.sh`, so a
   project's own `./engine.sh build` or `bash scripts/engine.sh` is refused as G-GATE-07 in every repo, including
   unrelated ones (CLAUDE.md rule 3), and without `.aiops/` the message names only `sdlc …`. → Refuse only the
   plugin's file: under `$CLAUDE_PLUGIN_ROOT` or `~/.claude/plugins/`, or resolving (with `cd`) to a file byte-equal
   to the plugin's `hooks/engine.sh`; negative tests in both repo kinds; name `hooks/engine.sh` in the message.
2. **[MEDIUM] the `systemMessage` split** (Security above).
3. **[LOW] `core.worktree`** (Security above).

## Other findings (non-blocking)
- [MINOR] `docs/architecture.md` Known gaps: name the `engine.sh` forms static parsing misses (a copy or link under
  another name, `bash < hooks/engine.sh`, `bash -c "$(cat …)"`).
- [MINOR] Lines over 120: the `_trust_lists` docstring (`setup.py:905`), two r8 lines in `docs/architecture.md`, two
  in `CHANGELOG.md`. → Rewrap.
- [MINOR] `cli.py:121` `PROFILE_RE` takes spaces only, not tabs or newlines (R-1 says "surrounding whitespace");
  logged r4/r5 because `engine.sh` sees them JSON-escaped. For the human's sign-off.
- [MINOR] Without `.aiops/`, G-GATE-07 sees `hook` only as a literal word; an assembled word (`ho$(echo o)k`) is the
  documented static-parsing gap.
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | Every AC met; the TUI check is still manual |
| Security | 25 | 21 | The `systemMessage` split, the `core.worktree` redirect |
| Test quality & test-first | 20 | 17 | Red runs throughout; the new guard has no false-positive tests |
| Plan conformance | 10 | 8 | The r8 guard is broader than its logged deviation |
| Maintainability | 5 | 4 | Long lines; the dormant-branch block reason |
| **Total** | 100 | **88** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the MAJOR and the MEDIUM block |
