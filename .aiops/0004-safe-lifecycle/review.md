---
id: 0004
verdict: PASS
commit: 238dd8f4018d386807588900557c36519c0e40b9
score: 92/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-06
---

# Review: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)

<!-- State 5 PRE-REVIEW of PR 2 (S5-S18; PR 1 = #11 was reviewed and merged separately), after three rounds by three
     fresh-context personas that did not write the code:
     - round 1 at 65872de: CHANGES_REQUESTED, 81/100
     - round 2 at c2ff018: verifier VERIFIED, code review PASS 88, security PASS 23/25
     - round 3 at 3baf28e: code review PASS 92, security PASS 24/25
     The pinned commit adds only a CHANGELOG known-issue line on top of 3baf28e. -->

## Summary
PR 2 adds:
- exact-command allowances, limited to two heuristic rules and never for a whole-environment dump
- install-state, adoption of older repos (`declined` for files the user removed, never for security scaffold)
- `list-installed`, `repair`, `upgrade` (pins only the plugin's own refs and shows every pin as a diff) and the
  human-only `uninstall`
- agent guards for those commands, and the configure skill
- conformance tests that run `upgrade` and `repair` mid-walk with real work, plus a permanent test that breaks
  `upgrade` on purpose and must catch each break by name

All round-1 and round-2 findings are fixed and verified by re-running the reviewers' reproductions. `make check`
passes (258 tests), and `make build` passes (warning: no icon). One LOW remains: the G-ENV-03 dump check works from a
list of known forms. It's deferred to intent 0005 and listed in the CHANGELOG. Verdict: **PASS**.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_lifecycle.py::InstallState::test_init_records_every_file`, `::test_stack_wiring_is_hashed_as_written`, `SetupState::test_setup_records_profile_and_stack` |
| AC-2 | ✅ met | `tests/test_lifecycle.py::ListInstalled::test_statuses_and_no_writes`, `::test_without_install_state` (adopt hint) |
| AC-3 | ✅ met | `tests/test_lifecycle.py::Repair::test_restores_missing_keeps_modified` |
| AC-4 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_replaces_stale_keeps_modified_bumps_ref` (byte-exact but for the ref, pin diff shown), `::test_pin_touches_only_zouj_refs`, `::test_pin_with_two_zouj_entries_and_another_marketplace` |
| AC-5 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_second_run_is_noop` |
| AC-6 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_dry_run_and_no_tty_write_nothing`, `Repair::test_dry_run_and_no_tty_write_nothing` |
| AC-7 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_agent_never_writes_human_owned`, `Repair::test_agent_env_cannot_lift_the_lock` |
| AC-8 | ✅ met | `tests/test_lifecycle.py::Adoption::test_alpha1_and_alpha2_repos_adopted`, `::test_upgrade_and_repair_end_to_end_on_a_release_repo`, `::test_security_scaffold_is_never_declined` |
| AC-9 | ✅ met | `tests/test_lifecycle.py::Ref::*` |
| AC-10 | ✅ met | `tests/test_lifecycle.py::Upgrade::test_legacy_approvals_listed_never_run`, `::test_agent_lists_migrations_but_never_runs_them` |
| AC-11 | ✅ met | `tests/test_lifecycle.py::Uninstall::test_removes_only_unmodified_managed` |
| AC-12 | ✅ met | `tests/test_lifecycle.py::Uninstall::test_tampered_state_refused` |
| AC-13 | ✅ met | `tests/test_lifecycle.py::Uninstall::test_agent_refused_dry_run_allowed`, `tests/test_guards.py::Lifecycle::test_uninstall_human_only` (incl. `# --dry-run`) |
| AC-14 | ✅ met | `tests/test_lifecycle.py::RoundTrip::test_init_upgrade_uninstall_dry_run` |
| AC-15 | ✅ met | `tests/test_guards.py::InstallState::test_agent_cannot_write_it` asserts the exact ids: G-ART-01 (Edit), G-ART-05 (shell) and G-FILE-04 (guard-files), as logged (review r2). Also `::Lifecycle::test_other_repo_refused` |
| AC-16 | ✅ met | shipped in #11; `tests/test_rules.py::Coverage::*`, `test_guards.py::Ids`, `test_shell_hooks.py::Ids` |
| AC-17 | ✅ met | shipped in #11; `tests/test_rules.py::Why::*` |
| AC-18 | ✅ met | `tests/test_shell_hooks.py::Allowance::test_heuristic_exact_command`, `::test_other_rules_still_run_after_an_allowance`, `tests/test_rules.py::Allowance::*` |
| AC-19 | ✅ met | `tests/test_shell_hooks.py::Allowance::test_gate_and_secret_entries_ignored`, `tests/test_rules.py::Allowance::test_full_environment_dump_never_allowed`, `tests/test_cli.py::Allowances::*` |
| AC-20 | ✅ met | `tests/test_playbook.py::Playbook::test_solo/team/strict` (mid-walk upgrade/repair with real work), `::Mutation::test_conformance_catches_broken_upgrade` (real gate opening, each break named) |
| AC-21 | ✅ met | `tests/test_lifecycle.py::Compat::test_alpha2_repo_unchanged` |
| AC-22 | ✅ met | `tests/test_rules.py::Registry::*`, `::History::test_current_scaffold_in_history` |
| AC-23 | ✅ met | `tests/test_rules.py::Skills::*`; `make build` passes |

## Security
- [LOW] `lib/sdlc_engine/rules.py` `dumps_environment()`: the check works from a list of known forms, so nested forms
  (`bash -c env`, `env env`, `xargs env`, `if …; then env; fi`) aren't recognised. A human who writes one of them into
  the human-owned `allowed-commands` lets the environment through. → Intent 0005 (item 6), and listed in the
  CHANGELOG known issues.
- [NIT] `REF_JSON_RE` would break JSON for a ref containing an escaped quote. Git refs can't contain `"`.
- Every round-1 and round-2 security finding is fixed and was re-verified by experiment: the bare-dump allowance, the
  env-lifted lock, `# --dry-run`, the symlinked `allowed-commands`, `pin()` scope and offsets, and declined security
  scaffold. The spec's flags (uninstall as a deletion primitive, allowances as a gate bypass, secret reads, upgrade as
  a downgrade path, ref trust, path leaks) are mitigated or documented as residual risks.
- Pre-existing gaps (unlocked `rm -rf ./`, shell writes in repos without `.aiops/`, archive extraction into
  `.aiops/config`, `/usr/bin/env`) are in intent 0005.

## Plan conformance
S1-S18 and S4b are done. The Deviation log holds 25 rows: every human decision (allowable set, G-ENV-04, version kept
at 0.2.0-alpha.2, open-question counting) and both rounds of review fixes. Not built: the install-state rows in
`doctor`, which are logged and listed as a known issue. NITs left as the author's call:
- `classify` trusts a matching version without checking the template; this only matters before the release bump.
- An unmanaged file with no ref gets a template diff on every upgrade.

## Test-first evidence
Every step commit and both fix commits carry a `Red:` line naming the failing test, and a `Green:` line with the
`make check` count (201 → 258). The tests that pass on first run have their red shown by a planted, reverted break:
- S4 coverage: a planted id
- S16 checker: a stub that returned nothing
- review r1 mid-walk: `agent_may_write → True`

The S17 commit was amended locally after `make check` caught a missing quick-reference entry; that is logged.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | every AC met |
| Security | 25 | 23 | the G-ENV-03 dump check works from a list of known forms (LOW, intent 0005) |
| Test quality & test-first | 20 | 18 | strong Red/Green; conformance with real work and a test that breaks upgrade on purpose |
| Plan conformance | 10 | 9 | thorough deviation log; doctor rows not built |
| Maintainability | 5 | 4 | `agent_may_write` modifies `os.environ` in process and restores it |
| **Total** | 100 | **92** | PASS: ≥ 80, no BLOCKER or HIGH, every AC met |
