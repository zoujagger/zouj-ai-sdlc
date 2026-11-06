---
id: 0004
verdict: CHANGES_REQUESTED
commit: 65872de9035c781277a557aadd7acbcf1769b711
score: 81/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-06
---

# Review: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)

<!-- State 5 PRE-REVIEW, round 1 of PR 2 (S5-S18; PR 1 = #11 was reviewed and merged separately). Written from the
     reports of three fresh-context personas that did not write the code. -->

## Summary
PR 2 adds:
- exact-command allowances
- install-state, adoption and the lifecycle commands (`list-installed`, `repair`, `upgrade`, `uninstall`)
- the agent guards for those commands
- the configure skill, the docs, and conformance tests across the profile walks

The design holds:
- `uninstall`'s triple condition and no-link removal
- allowances limited to two heuristic rules
- human-owned files never written by the agent
- `make check` green (249 tests), `make build` passes

But the code reviewer reproduced one **HIGH** bug. `upgrade` rewrites every `"ref"` in a JSON file, so a second
marketplace in `.claude/settings.json` gets the zouj sha, and the preview never shows the pin. That breaks AC-4 in a
realistic configuration. The security reviewer found a **MEDIUM** issue: an allowance can let a full `printenv` dump
through, against the spec's "secret reads via allowance" flag. Several tests also prove less than their AC. Verdict:
**CHANGES_REQUESTED**. The fixes are small and listed under Security and Plan conformance.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_lifecycle.py::InstallState::test_init_records_every_file`, `::test_stack_wiring_is_hashed_as_written`, `SetupState::test_setup_records_profile_and_stack` |
| AC-2 | ✅ met | `tests/test_lifecycle.py::ListInstalled::test_statuses_and_no_writes` |
| AC-3 | ✅ met | `tests/test_lifecycle.py::Repair::test_restores_missing_keeps_modified` |
| AC-4 | ❌ not met | `tests/test_lifecycle.py::Upgrade::test_replaces_stale_keeps_modified_bumps_ref` passes, but asserts only `endswith("# ours")`. Reproduced: a second `"ref"` in `.claude/settings.json` is rewritten, and an expression-valued `ZOUJ_SDLC_REF: ${{ … }}` line is corrupted (`lifecycle.py:154-155`, `pin()` at `:397`) |
| AC-5 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_second_run_is_noop` |
| AC-6 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_dry_run_and_no_tty_write_nothing`, `Repair::test_dry_run_and_no_tty_write_nothing` |
| AC-7 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_agent_never_writes_human_owned` |
| AC-8 | ⚠️ partial | `tests/test_lifecycle.py::Adoption::test_alpha1_and_alpha2_repos_adopted` checks `adopt()` directly. No test runs `upgrade`/`repair` end to end on an alpha-built repo. Reproduced: a user-deleted `deploy.yml` is re-created as `new` after adoption |
| AC-9 | ✅ met | `tests/test_lifecycle.py::Ref::*` (the `!` prefix isn't asserted) |
| AC-10 | ⚠️ partial | `tests/test_lifecycle.py::Upgrade::test_legacy_approvals_listed_never_run`: human run only; "human or agent" is not tested under `CLAUDECODE=1` |
| AC-11 | ✅ met | `tests/test_lifecycle.py::Uninstall::test_removes_only_unmodified_managed` |
| AC-12 | ✅ met | `tests/test_lifecycle.py::Uninstall::test_tampered_state_refused` |
| AC-13 | ✅ met | `tests/test_lifecycle.py::Uninstall::test_agent_refused_dry_run_allowed`, `tests/test_guards.py::Lifecycle::test_uninstall_human_only` (a `# --dry-run` comment bypasses the guard layer: Security, LOW) |
| AC-14 | ✅ met | `tests/test_lifecycle.py::RoundTrip::test_init_upgrade_uninstall_dry_run` |
| AC-15 | ✅ met | `tests/test_guards.py::InstallState::test_agent_cannot_write_it`, `::Lifecycle::test_other_repo_refused` (G-ART as well as G-FILE ids, logged S8) |
| AC-16 | ✅ met | shipped in #11; `tests/test_rules.py::Coverage::*`, `test_guards.py::Ids`, `test_shell_hooks.py::Ids` hold at HEAD |
| AC-17 | ✅ met | shipped in #11; `tests/test_rules.py::Why::*` |
| AC-18 | ✅ met | `tests/test_shell_hooks.py::Allowance::test_heuristic_exact_command`, `::test_other_rules_still_run_after_an_allowance`, `tests/test_rules.py::Allowance::*` |
| AC-19 | ✅ met | `tests/test_shell_hooks.py::Allowance::test_gate_and_secret_entries_ignored`, `tests/test_cli.py::Allowances::*` (allowable set per the human's PR 1 decision) |
| AC-20 | ⚠️ partial | `tests/test_playbook.py::Playbook::test_solo/team/strict`, `::Mutation::test_conformance_catches_broken_upgrade`. The mid-walk upgrade/repair have nothing to do (trivially true). The "opens a gate" break never opens the gate (a fake hash). The subtests don't assert which break was named |
| AC-21 | ✅ met | `tests/test_lifecycle.py::Compat::test_alpha2_repo_unchanged` |
| AC-22 | ✅ met | `tests/test_rules.py::Registry::*`, `::History::test_current_scaffold_in_history` |
| AC-23 | ✅ met | `tests/test_rules.py::Skills::*`; `make build` passes (icon warning only) |

## Security
- [HIGH] `lib/sdlc_engine/lifecycle.py:155,397`: `pin()` rewrites every `"ref"` key, not only the zouj marketplace's,
  and the plan doesn't diff pinned files. A team's other marketplace silently moves to a nonexistent commit. → Pin
  only `extraKnownMarketplaces.zouj.source.ref`, show `show_diff(disk, pinned)` for every pin, and add a test with a
  second marketplace.
- [MEDIUM] `lib/sdlc_engine/lifecycle.py:154`: `REF_LINE_RE` rewrites a non-literal `ZOUJ_SDLC_REF: ${{ … }}` into
  broken YAML. → Pin only literal values (`v…`, a 40-hex sha, the placeholder); list any other value for the human.
- [MEDIUM] `lib/sdlc_engine/rules.py` `allowed()`: an entry `G-ENV-03 printenv` (or bare `env`) lets the full
  environment, every token included, into the session, against the spec flag "secret reads via allowance". → Refuse
  an allowance for a bare dump (`env`/`printenv` with no operand, `env` without a command), and report it in
  `allowance_problems()`.
- [LOW] `lib/sdlc_engine/lifecycle.py` `agent_may_write` → `machine.lock()`: an inline `SDLC_HOOK_PROFILE=spike` or
  `AIOPS_INTENT=…` before the agent's `sdlc repair|upgrade` lifts the read-only lock for that run, and the guard
  allows the line. → Refuse those assignments with lifecycle commands (G-SCAF-01) and test it. The same root cause in
  `init --force` goes to intent 0005.
- [LOW] `lib/sdlc_engine/guards.py:378,421`: `sdlc uninstall --yes # --dry-run` passes G-GATE-07 (the CLI still
  refuses). → Cut the arguments at an unquoted `#`.
- [LOW] `lib/sdlc_engine/cli.py` doctor and `validate --ci` read `allowed-commands` through a symlink and echo
  unrecognised lines in full. → Same `is_file() and not is_symlink()` check as `allowed()`; report line numbers, not
  raw text.
- Pre-existing, for intent 0005: `tar -x`/`unzip` into the working directory, `git stash pop` and `git pull` can write
  `.aiops/config/*`.

## Plan conformance
S1-S18 and S4b match the diff. All 22 deviations are logged, including the human decisions (narrowed allowable set,
G-ENV-04, version kept at 0.2.0-alpha.2, open-question counting). Not built: the install-state rows in `doctor`
(logged; known issue). Found missing, to fix:
- `list-installed` without install-state should say how to adopt (R-2).
- The plan's Risks row promised that the ref rewrite would be "shown in the diff before confirmation"; it isn't.
- After adoption, a scaffold path the user deleted shouldn't be re-created as `new` (code review MEDIUM).

## Test-first evidence
Every step commit (S5-S18, plus `65872de`) carries a `Red:` line naming the failing test and the failure: a missing
attribute, an unknown command, exit 0 where 2 was expected, and for S16 a stubbed `playbook_violations` that returned
`[]` for all three planted breaks. Each also carries a `Green:` line with the `make check` count, which rises from 201
to 249. The S17 amend, which added a missing quick-reference entry caught by `make check`, is logged.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 32 | AC-4 not met; AC-8, AC-10, AC-20 partial; R-2 adopt hint missing |
| Security | 25 | 21 | HIGH pin scope (also an AC-4 failure), MEDIUM bare-dump allowance, LOW env lock bypass |
| Test quality & test-first | 20 | 14 | strong Red/Green; the conformance and mutation tests are weaker than planned |
| Plan conformance | 10 | 9 | deviations thorough; the Risks promise (pin diff) wasn't kept |
| Maintainability | 5 | 5 | |
| **Total** | 100 | **81** | CHANGES_REQUESTED: a HIGH finding and an unmet AC |
