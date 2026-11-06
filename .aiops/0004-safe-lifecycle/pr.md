<!-- PR description for intent 0004, generated in state 5. `gh pr create --body-file` it. -->
## feat: safe lifecycle: install state, upgrade, repair, uninstall, allowances (0004 PR 2)

**Intent:** `.aiops/0004-safe-lifecycle/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 92/100 at `238dd8f` (three rounds; verifier, code reviewer and security reviewer in fresh contexts.
Security 24/25.)

PR 2 of 2 for roadmap Phase 2. PR 1 (#11, rule ids and `sdlc why`) is merged. The version stays 0.2.0-alpha.2; these
changes sit under `[Unreleased]`, planned as 0.2.0-alpha.3.

### What and why
After setup, nothing managed a repo's install. This PR makes the plugin know what it installed, upgrade and repair it
safely, and give false positives an outlet that can't touch a gate:
- **Exact-command allowances.** In `.aiops/config/allowed-commands` (human-owned), only for the two heuristic rules:
  `G-ENV-03` (env/printenv) and `G-BASH-07` (sudo, mkfs, dd, chmod 777).
  - One exact command lifts one rule, and every other rule still runs.
  - A whole-environment dump can never be allowed.
  - `doctor` and `validate --ci` (head and base) reject anything else.
  - There is no per-rule disable switch (ADR 0002).
- **`.aiops/install-state.json`.** `init` and `setup` write it, recording the version, ref, profile, stack and file
  hashes. The engine owns it; the agent can't edit it, and CODEOWNERS covers it.
- **`sdlc list-installed`** shows each file as current, stale, modified, missing, unmanaged, dropped, new or declined.
- **`sdlc repair`** restores missing files and never touches modified ones.
- **`sdlc upgrade`:**
  - replaces stale files, showing a diff
  - keeps modified files except their CI ref
  - pins only literal `ZOUJ_SDLC_REF` values and the zouj marketplace's ref to the plugin's full commit sha, each
    shown as a diff
  - lists migrations; `legacy-approvals` is human-only and never run
- **`sdlc uninstall`** is human-only. It removes only recorded, released, unmodified scaffold files, never
  `.aiops/NNNN-*`.
- **Adoption.** Repos from 0.1.0 and the alphas are adopted from `defaults/scaffold-history.json`, which
  `scripts/scaffold-history.py` builds. Files the user had removed become `declined` and are never re-created. That
  never applies to the CI audit, CODEOWNERS or the signer and secret lists.
- **The agent and these commands:**
  - They act only in the session's repo (G-SCAF-01).
  - They never write human-owned files or code under the read-only lock, and an inline
    `SDLC_HOOK_PROFILE=`/`AIOPS_INTENT=` can't lift the lock for them.
  - A real `uninstall` is blocked for the agent (G-GATE-07).
- **`/zouj-ai-sdlc:configure`.** A read-only preview of a profile change that hands you the terminal command.
- **Status.** `sdlc status` counts open questions only where they can still block a gate.

### Acceptance criteria
- [x] AC-1: init records install-state (`tests/test_lifecycle.py::InstallState`)
- [x] AC-2: `list-installed` statuses, read-only (`::ListInstalled`)
- [x] AC-3: `repair` restores missing, keeps modified (`::Repair`)
- [x] AC-4: `upgrade` replaces stale, keeps modified byte-exact but the ref, pins every ref (`::Upgrade`)
- [x] AC-5: a second `upgrade` is a no-op (`::Upgrade::test_second_run_is_noop`)
- [x] AC-6: dry run and no terminal write nothing (`::Upgrade`, `::Repair`)
- [x] AC-7: run by the agent, human-owned files are never written (`::Upgrade::test_agent_never_writes_human_owned`)
- [x] AC-8: alpha.1/alpha.2 repos adopted, end to end (`::Adoption`)
- [x] AC-9: ref resolution order (`::Ref`)
- [x] AC-10: `legacy-approvals` listed, never run, human or agent (`::Upgrade`)
- [x] AC-11, AC-12, AC-13: uninstall is exact, refuses a tampered state, is human-only (`::Uninstall`,
  `tests/test_guards.py::Lifecycle`)
- [x] AC-14: init → upgrade → uninstall --dry-run round trip (`::RoundTrip`)
- [x] AC-15: install-state is engine-written (`tests/test_guards.py::InstallState`)
- [x] AC-16, AC-17: rule ids and `sdlc why` (PR 1, still green)
- [x] AC-18, AC-19: allowances exact, never for a gate, secret or dump (`tests/test_shell_hooks.py::Allowance`,
  `tests/test_rules.py::Allowance`, `tests/test_cli.py::Allowances`)
- [x] AC-20: playbook conformance mid-walk, and a permanent test that breaks upgrade on purpose
  (`tests/test_playbook.py`)
- [x] AC-21: alpha.2 repos work unchanged (`tests/test_lifecycle.py::Compat`)
- [x] AC-22: registry and scaffold history checked by `make check` (`tests/test_rules.py::Registry`, `::History`)
- [x] AC-23: configure skill is read-only (`tests/test_rules.py::Skills`)

`make check`: 258 tests pass. `make build`: passes (warning: no icon, Phase 3).

### Deviations from plan
The plan.md Deviation log has 24 rows. The ones that matter most:
- **Allowable set narrowed** to G-ENV-03 and G-BASH-07. G-ENV-04 (echoing secrets) was split out.
- **The version stays 0.2.0-alpha.2** until the release.
- **`sdlc status`** counts open questions only for gates that are still closed.
- **`doctor`'s install-state rows weren't built.** They are listed as a known issue.
- **Both review rounds' fixes:**
  - the scoped, diffed ref pin
  - `declined`
  - dump-proof G-ENV-03
  - an env-proof lock
  - a guard that can't be fooled by a comment
  - stronger conformance tests

### Risks and rollback
- **Risks:** the pin rewrites human-owned files. It writes only the plugin's own refs, shows them as a diff first,
  and only a human run writes them. `uninstall` deletes files, but only with the triple condition and only when the
  human runs it.
- **Known issues, deferred to intent 0005:**
  - the G-ENV-03 dump check works from a list of known forms
  - unlocked `rm -rf ./` and deleting a parent directory of a protected path
  - shell writes in repos without `.aiops/`
  - archive extraction into `.aiops/config`
- **Rollback:** reinstall the 0.2.0-alpha.2 plugin. Older engines ignore install-state, and deleting
  `.aiops/install-state.json` and `allowed-commands` brings a repo back to the alpha.2 shape.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
