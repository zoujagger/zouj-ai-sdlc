---
id: 0007
verdict: CHANGES_REQUESTED   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: f38003bafd902ea9ad64c9cdab901f6a67cef505
score: 92/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-16
---

# Review: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 5 PRE-REVIEW. Written from the reports of three fresh-context personas that did not write the code.
     Rounds 1-3 reviewed the removed `Setup Profile` phrase (PASS 86, 88, 92). Round 4 (a693a2f): CHANGES_REQUESTED 89.
     Round 5 (53c90c0): CHANGES_REQUESTED 87. Round 6: fixed in e704354. Round 7: PASS 92, its LOWs and NITs fixed
     in f38003b. Round 8 at f38003b (this file). Diff against origin/main. -->

## Summary
0007 adds three things:
- **Profile by the typed setup command.** In a fresh repo, `/zouj-ai-sdlc:setup solo|team|strict` first writes
  the core scaffold, then sets the first profile and commits `.aiops/config.json` alone.
- **`sdlc where`.** It prints the terminal command, and the state card shows it.
- **A core-only scaffold.** The default installs only `core`; the other parts are opt in with `--with`.

It ships as 0.2.0-alpha.4.

Round 8 results:
- **Verifier:** VERIFIED. All 23 ACs have passing tests. `make check` (429), `make build` (2 old warnings) and
  `sdlc validate 0007` pass.
- **Code-reviewer:** PASS 95/100, no BLOCKER or MAJOR, three MINOR.
- **Security-reviewer:** PASS, 20/25, no CRITICAL or HIGH, **one MEDIUM (reproduced)**, two LOW.

**Verdict: CHANGES_REQUESTED.** Every AC is met and the total is 92, but the MEDIUM is a working bypass of the r7
G-GATE-07 fix, and the docs claim the opposite. As in round 5, a MEDIUM blocks PASS.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py:1352`; `tests/test_cli.py:531` |
| AC-2 | ✅ met | `tests/test_playbook.py:344 CommandWalk` (inherits `test_solo` at `:328`; every prompt through `engine.sh` with both markers) |
| AC-3 | ✅ met | `tests/test_setup.py:1399`, `:1404`, `:1415`, `:1426`; `tests/test_cli.py:578` |
| AC-4 | ✅ met | `tests/test_cli.py:547` (11 forms, empty output), `:564`, `:572` |
| AC-5 | ✅ met | `tests/test_shell_hooks.py:691` (fake plugin logs every python start; compact payload) |
| AC-6 | ✅ met | `tests/test_cli.py:599` |
| AC-7 | ✅ met | `tests/test_cli.py:621` |
| AC-8 | ✅ met | `tests/test_setup.py:1529`, `:1536` (bytes, `:1546`), `:1555`, `:1303` |
| AC-9 | ✅ met | `tests/test_cli.py:675` |
| AC-10 | ✅ met | `tests/test_cli.py:722`, `:739`, `:748`, `:779` |
| AC-11 | ✅ met | `tests/test_cli.py:412`; `tests/test_setup.py:973` |
| AC-12 | ✅ met | `tests/test_cli.py:421`, `:431`, `:436`, `:447`; `tests/test_setup.py:1008` |
| AC-13 | ✅ met | `tests/test_lifecycle.py:767`, `:779` |
| AC-14 | ✅ met | `tests/test_lifecycle.py:713`; `tests/test_cli.py:454`, `:461` |
| AC-15 | ✅ met | `tests/test_lifecycle.py:834`, `:844`, `:851`, `:855` |
| AC-16 | ✅ met | `tests/test_playbook.py:338 CoreWalk`, `:344 CommandWalk` × solo/team/strict |
| AC-17 | ✅ met | `tests/test_cli.py:802`; no `defaultMode` in the scaffold settings |
| AC-18 | ✅ met (amended AC) | `tests/test_setup.py:895`; `tests/test_cli.py:814`, `:831`, `:847`, `:858`, `:990`. `Setup Profile` appears only as R-4's commit title |
| AC-19 | ✅ met | `plugin.json` `0.2.0-alpha.4`; `tests/test_cli.py:906`; `tests/test_rules.py:326`; `tests/test_setup.py:918`; `make build` passes |
| AC-20 | ✅ met | `tests/test_cli.py:470`, `:485` |
| AC-21 | ✅ met (run quoted below) | `tests/test_cli.py:936`; `evals/README.md:22` |
| AC-22 | ✅ met | `tests/test_setup.py:1077`, `:1152` |
| AC-23 | ✅ met | `tests/test_setup.py:1164` (not a git repo, `$HOME`, `GIT_DIR`, Preflight ✗), plus the below-the-top and repo-config refusals (r5 fix) |

**AC-21: the run** (plan.md Deviation log S19, 2026-11-13; `--allow-tools Bash Write Edit`, 3 runs per arm):
`profile-by-setup-command` 1.00 with the plugin (asks-for-setup-command PASS ×3, config-unchanged ✓ ×3), 0.67
without, Δ +0.33, $0.87.

## Security
Closed since round 5: the unpinned git on the fresh-repo path, warnings only through the agent (`systemMessage`),
`sdlc hook prompt` in a repo without `.aiops/` (r7, G-GATE-07 before the uninitialized return), the commit re-reading
the file (r7, `_commit_alone(data=)`).

Round 8 findings:
- [MEDIUM, reproduced] `lib/sdlc_engine/guards.py:294-305`: `ENGINE_RES` has no pattern for the plugin's hook
  wrapper, so `printf '{"prompt":"/zouj-ai-sdlc:setup solo"}' | <plugin>/hooks/engine.sh prompt` (and
  `$CLAUDE_PLUGIN_ROOT/hooks/engine.sh prompt`) pass `check_bash` (rc 0) where every `sdlc hook prompt` form gives
  rc 2. Run for real in a scratch repo, it wrote the core scaffold and committed `chore(aiops): Setup Profile solo`;
  the `systemMessage` went to the agent. In an initialized repo a fed `Plan Approved NNNN` is also allowed (already
  so on main), which under `solo` opens a gate with no nested session. `docs/architecture.md` and spec flag 3 say
  such a payload "is refused by G-GATE-07 in every repo". → Test-first: add the `engine.sh` forms (bare, `bash`/`sh`/
  `source`/`.`, `$CLAUDE_PLUGIN_ROOT/…`) to `test_hook_only_commands_blocked_without_aiops` and an initialized-repo
  case with an approval phrase; then treat any run of `hooks/*.sh` hook scripts as hook-only in `ENGINE_RES`.
- [LOW] An agent-run hook (this route, or `claude -p`) leaves the human only one commit; the `systemMessage`
  reaches the agent. → Closing the MEDIUM covers `engine.sh`; say in Known gaps that the warnings reach a human only
  in the human's own session.
- [LOW] `lib/sdlc_engine/setup.py` `_trust_lists`: no size cap, so a huge planted `allowed-commands` can bury the
  warnings in `additionalContext`/`systemMessage`. → At most ~20 lines per list, then "(+N more, see <file>)".

Spec flags (security-reviewer):

| Flag | Mitigated? | Evidence |
|---|---|---|
| A hook writes a human-owned file | Partly | `no_profile_yet`, `approval_in_history`, session-repo check, single-file commit of the written bytes, `local_config_keys` first. Weakened by the MEDIUM |
| The hook writes the core scaffold without a preview (R-2a) | Yes | `scaffold_first`: `scaffold_root_problem`, history, quick Preflight ✗, `symlink_refusal`, create-only `write_file`, top of the work tree only; reply lists every file |
| The agent prompts a session of its own | Accepted residual, overstated | G-GATE-07 covers `sdlc hook`, not `hooks/engine.sh prompt` (MEDIUM) |
| The agent asks the human to type the command | Yes | skill text; a bare command previews |
| The profile commit is unsigned in team/strict | Yes, as designed | opens no gate; CI reads the base config |
| `sdlc where` prints a home path | Yes | local only |
| A core-only repo lacks the AI review and scheduled scan | Yes | preview and `list-installed` name the parts left out |
| No change to secrets, lock, approval path, audit, allowed-commands | Yes | `approvals.py` adds only the `data=` blob path; `guards.py` only widens G-GATE-07 |

## Plan conformance
- **Steps:** all 20 are done and match the diff.
- **Deviation log:** every divergence is logged, including the r6 and r7 rows (G-GATE-07 before the initialized
  check, `_commit_alone(data=)`, `classify` reporting template-plus-profile as current, `engine.sh`'s
  `[[:space:]]+`).
- **Scope:** nothing ships outside it.

## Test-first evidence
Every step and review fix records its red run (`Red:` in the commit body or the Deviation log row): S1-S20, r1, r2,
r4 `c29390f`, r5 `f828256`, r6 `e704354` (5 tests), r7 `f38003b` (5 tests). Two tests were never red and say so:
S17 `CommandWalk` (behaviour shipped in S14/S16) and the AC-8 byte comparison (equal by construction).

## Fixes requested
1. **[MEDIUM] `hooks/engine.sh` run by the agent bypasses G-GATE-07** (Security above). Test-first, then
   `ENGINE_RES`; correct `docs/architecture.md` and the Known gaps.
2. **[MINOR] G-GATE-07 now acts in every repo, but is still documented as a gate rule.** `defaults/rules:17`
   (class `gate`, stage `intent-spec-plan`), `docs/architecture.md:35` ("only those safety checks"), `CLAUDE.md`
   rule 3, the CHANGELOG. All of `ENGINE_RES` now runs in unrelated repos, so by reading the regexes
   `git commit -m "docs: the sdlc close step"` or `git ls-files | xargs grep -l sdlc` would be blocked there with no
   `allowed-commands` escape. → Restrict the uninitialized branch to the hook-feeding forms (`ENGINE_RES` [0]-[3],
   `_dynamic_engine_call`, the new `engine.sh` pattern) or accept the scope; set the stage to every repo; update the
   docs.
3. **[MINOR] `lib/sdlc_engine/setup.py:836-837`:** `lifecycle.record` hashes the config on disk after the write,
   not the bytes the hook wrote, so a racing rewrite is recorded as `current`. → Record the sha of `data`; assert
   it in `FirstRun::test_commit_holds_the_bytes_the_hook_wrote`.

## Other findings (non-blocking)
- [MINOR] `lib/sdlc_engine/lifecycle.py:245-246`: `classify` now calls a template-plus-one-profile config `current`
  regardless of install-state. Safe today (`MERGED_JSON` is only pinned by `plan_upgrade`; `plan_uninstall` compares
  hashes). → Document it, or test that `upgrade --yes` keeps `profile: solo`.
- [LOW] `_trust_lists` size cap (Security above).
- [NIT] `CHANGELOG.md` `[0.2.0-alpha.4]`: the summary and the Upgrading paragraph still say "typed phrase"; name the
  `/zouj-ai-sdlc:setup <profile>` command.
- [NIT] `hooks/engine.sh`'s pre-filter matches the command anywhere in the raw payload, not only in `prompt`; the
  engine's anchored `PROFILE_RE` still decides, so the cost is only a python start.
- **Human, before the merge:** type `/zouj-ai-sdlc:setup solo` once in a `make dev` session in a scratch repo (the
  live check so far was a `claude -p` probe with a throwaway plugin).

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 39 | Every AC met; the install-state hash race |
| Security | 25 | 20 | Lower of the two reviewers' scores (20 and 23): the `engine.sh` bypass, the trust-list cap |
| Test quality & test-first | 20 | 19 | Red runs recorded throughout; no `engine.sh` form in the hook-only tests |
| Plan conformance | 10 | 10 | All divergences logged |
| Maintainability | 5 | 4 | G-GATE-07's registry and docs lag its new scope |
| **Total** | 100 | **92** | PASS needs ≥ 80, no BLOCKER or HIGH, every AC met; the MEDIUM blocks, as in round 5 |
