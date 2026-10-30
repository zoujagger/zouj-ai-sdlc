---
id: 0001
title: zouj-ai-sdlc plugin
status: Approved
spec: ./spec.md
created: 2026-10-30
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-10-30T14:53:44Z
approved-via: cli
approved-sha256: c0252e785633b2de6a1e236cc742debaa3c14bd56bc4d8f2e696d8569a53deb8
---

# Plan: zouj-ai-sdlc plugin

## Approach
Accepted in Claude Code Plan mode on 2026-10-30 (`~/.claude/plans/act-as-a-senior-adaptive-scone.md`). Build the plugin
alongside the template (copy, don't move, the guarded files), test-first for the engine and guards, then stage a
cutover that the human applies.

## Steps
- [x] **S1**: manifests: `.claude-plugin/plugin.json`, `marketplace.json` (AC-1)
- [x] **S2**: state engine `lib/sdlc_engine/*`, `bin/sdlc`, `schemas/*.json`, artifact templates (AC-2, AC-5, AC-6, AC-10)
  - Test first: `tests/test_engine.py`
- [x] **S3**: hooks: `hooks/hooks.json`, guards ported to `.aiops/`, plus approval/lock guards (AC-3, AC-4, AC-7, AC-8, AC-11)
  - Test first: `tests/test_guards.py`, `tests/test_shell_hooks.py`
- [x] **S4**: skills and agents rewritten for the state machine; bootstrap skill; `/init` (AC-9)
- [x] **S5**: consumer scaffold `templates/scaffold/` incl. `aiops-gates.yml` (AC-9, AC-10)
- [x] **S6**: evals in `claude plugin eval` format; docs, README, CHANGELOG; dev Makefile
- [x] **S7**: cutover script `.update/apply.sh` (the human runs it) (AC-1)

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bash write detection misses an interpreter write | high | medium | CI audit; documented as a deterrent |
| A guard crash blocks every tool call | low | high | fails closed with a clear message; tests for every hook |
| Live template hooks block the migration | high | low | stage changes; the human applies them externally |

## Test definitions
| AC | Test | Type | Proves |
|---|---|---|---|
| AC-1 | `claude plugin validate .` | cli | manifest and layout valid |
| AC-2 | `test_engine.States.test_walks_the_five_states` | unit | derived states |
| AC-3 | `test_guards.EditGuard.test_agent_cannot_approve_by_editing`, `PromptAndSessionHooks.*` | hook | only the human phrase opens gates |
| AC-4 | `test_guards.BashGuard.test_read_only_state_blocks_shell_writes_to_code`, `EditGuard.test_code_is_read_only_until_plan_approved` | hook | read-only lock |
| AC-5 | `test_guards.EditGuard.test_artifacts_are_created_in_order_and_as_draft` | hook | creation order |
| AC-6 | `test_engine.States.test_editing_an_approved_spec_reopens_the_gate`, `Artifacts.test_plan_hash_*` | unit | stale approvals |
| AC-7 | `test_engine.States.test_review_goes_stale_when_code_changes`, `BashGuard.test_merging_on_main_*` | unit | final gate |
| AC-8 | `test_shell_hooks.ShellHooks.test_dormant_without_aiops`, `EditGuard.test_uninitialized_repo_is_untouched` | hook | dormancy |
| AC-9 | `test_cli.Init.*` | cli | scaffold is non-destructive |
| AC-10 | `test_engine.Approvals.test_ci_audit_accepts_human_and_rejects_agent_approvals` | unit | CI audit |
| AC-11 | `test_shell_hooks.ShellHooks.test_guard_*` | hook | ported guards unchanged |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-10-30 | S2 | Schemas are JSON, not YAML | hooks must run on stdlib only (pyyaml may be missing) | |
| 2026-10-30 | S2 | Tests use stdlib unittest, not pytest | pytest isn't installed; there's no new dependency | |
| 2026-10-30 | S3 | No plugin-shipped permission allow-rules | plugin settings.json supports only `agent` and `subagentStatusLine`; `/init` prints the rules to add | |
| 2026-10-30 | S3 | The approval CLI refuses on CLAUDECODE / CLAUDE_CODE_CHILD_SESSION; the prompt hook calls the engine in-process | CLAUDECODE=1 is also set for hook processes | |
| 2026-10-30 | S4 | `/verify` folded into `/zouj-ai-sdlc:review`; `/sdlc` renamed `status`; `sdlc-worktree` added to bin/ | the protocol's state 5 includes verification; `bin/` is on PATH | |
| 2026-10-30 | S5 | Consumer workflows load the plugin via claude-code-action `plugins` inputs (marked: check the input names) | CI agents need the same skills and guards | |
| 2026-10-30 | S6 | Evals use case.yaml + fixture.sh (`--scaffold`); dev sessions use `make dev`, not enabledPlugins in settings | the plugin-eval format; a relative directory-marketplace path in settings is unverified | |
| 2026-10-30 | S6 | Plugin CI installs Claude Code with npm, not the piped install script | supply-chain hygiene | |
| 2026-10-30 | S3 | The approval phrase is case-insensitive, the id is optional (defaults to the active intent), and a trailing `.`/`!` is allowed; it must still be the whole prompt | usability; a phrase quoted inside a sentence is still ignored | |
| 2026-10-30 | S3 | Verifier findings fixed: `hooks/engine.sh` fails closed if the engine can't start; the CI audit checks a single-file commit, the matching sha256 and optional signing (`require_signed_approvals`); git rm/mv/checkout/restore of artifacts is blocked; tests added for AC-5/AC-8 and state 0 | fresh-context /verify returned NOT VERIFIED | |
| 2026-10-30 | S5 | The consumer `aiops-gates.yml` pins the engine (`ZOUJ_SDLC_REF: v0.1.0`) | supply chain: never run an unpinned main in a required check | |
| 2026-10-30 | S3 | The bash guard tracks `cd`, inspects `bash -c`/`sh -c`/`eval` recursively, reads `git commit -F` files, blocks path-style `git checkout` while locked, and blocks `gh api …/merge`; tests added (incl. `validate --ci` through the CLI) | second /verify: a reproducible `cd src && … ../.aiops/…` bypass | |
