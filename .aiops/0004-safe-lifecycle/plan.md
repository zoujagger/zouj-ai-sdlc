---
id: 0004
title: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)
status: Approved
spec: ./spec.md
created: 2026-11-06
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-06T08:39:04Z
approved-via: cli
approved-sha256: af7ba82196cf502021ae9d1960d65edea4a996d546eae2092ea2a56c0d24f59f
---

# Plan: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
**Decisions made at the spec gate (zoujagger, 2026-11-06).** They are recorded here because changing the approved
spec.md would close its gate again:
- **Rule classes:** as proposed in the spec's Open questions. Only these `heuristic` rules can get an allowance:
  - `re_rm_root`
  - `re_dump_env`
  - `re_system`
  - `re_pipe_sh`
  - the nested-shell depth rule (`guards.py`, `"bash"`)

  Everything else is `gate`, `secret`, `toolchain` or `safety`.
- **The `v0.2.0-alpha.2` tag:** created on `0f8d4f6`, the PR #9 merge that the installed alpha.2 records as
  `gitCommitSha`. It's annotated and local, and gets pushed with the release. `scaffold-history.py` reads `v0.1.0`,
  `v0.2.0-alpha.1` and `v0.2.0-alpha.2` from tags.
- **`/zouj-ai-sdlc:configure`:** a thin wrapper (R-13).

**Decisions made at the plan gate (zoujagger, 2026-11-06):**
- **S16 gets a permanent test that breaks `upgrade` on purpose.** The playbook checks are factored into
  `playbook_violations(root, before)`. A test patches `upgrade` in-process so it breaks the playbook in three ways
  (opens a gate, deletes an artifact, writes code while the lock is on), and asserts that each break is reported.
- **`upgrade` never merges files automatically.** In a modified file it rewrites only the ref line and prints a
  diff for everything else.
- **Two PRs:**
  - **PR 1** has the approval commits and S1-S4 (rule ids, with no behaviour change). It goes from branch
    `feat/0004-rule-ids` after a fresh-context review of that diff, and the human merges it.
  - **PR 2** has S5-S18 on `feat/0004-safe-lifecycle`, rebased on main after PR 1 merges. It carries `review.md`
    and `pr.md` for the whole intent.

  The review for PR 1 goes in the PR description, not in `review.md`, because `review.md` reviews the whole intent
  and its `commit:` must be PR 2's head.

**Build order.** The registry and the ids come first (S1-S4). They touch every guard and carry no behaviour change,
so they're easiest to review on their own, and the allowance (S5-S7) builds on the class lookup. Then install-state
and its readers (S8-S10). Then the writing commands, from least to most dangerous: repair, ref, upgrade, uninstall
(S11-S14). Then the guard extensions, the playbook conformance, and the skill and docs (S15-S18). Every engine and
guard change is test-first (CLAUDE.md rule 2).

**Code to reuse:**
- `cli.write_file`, `symlink_on_path` and `scaffold_root_problem` (`lib/sdlc_engine/cli.py`, ~l.300-365): every
  lifecycle write and refusal.
- `cli.init_actions` / `apply_init` (`cli.py` ~l.378-440): the scaffold walk and `REF_PLACEHOLDER` substitution.
  Moved into `lifecycle.render(rel, ref)`.
- `cli._wire_stack` (`cli.py:278`): split into a pure `wire(src, stack) -> (src, wired)`, so adoption can recognise
  stack-wired Makefiles.
- `setup.apply` (`setup.py:424`): records install-state after the config merge and stack wiring, from the bytes on
  disk.
- `setup.parse` / `_confirm` / `_is_tty` (`setup.py:317-420`): option parsing and the single confirmation for
  repair, upgrade and uninstall.
- `approvals.running_under_agent()` and `HUMAN_ONLY` (`cli.py`): the human-only uninstall.
- `approvals` base-ref reader (`approvals.py:272`, `git show <base>:<rel>`): `validate --ci` reads
  `allowed-commands` from the base.
- `approvals.unsigned_approvals`: the `legacy-approvals` migration.
- `guards._block(rule, reason, procedure)` (`guards.py:32`): the rule label becomes the id.
- `guards._scaffold_elsewhere` / `SCAFFOLD_RE` / `ENGINE_RES` (`guards.py:180-206, 380`): extended for the new
  commands.
- `tests/helpers.py` (`ROOT`, `SDLC`, the repo fixtures) and `tests/test_setup.SetupCase`: fixtures.
  `tests/test_playbook.Playbook`: the per-profile walk.

## Steps
- [x] **S1**: Rule registry and `sdlc why`.
  - Create `defaults/rules`: `<id> <class> <stage> <summary…>`, one line per rule in today's guards. Every
    `_block` call in `guards.py`, every `block` call in `hooks/*.sh`, `secret_scan.main`, `cli.hook`'s fail-closed
    path, `lib.sh` `fail_closed`/`secret_scan`, `engine.sh` and `stop-verify.sh` gets its own id.
  - Create `defaults/rules.md`: one `## <id>` section per rule (why, stage, safe alternative).
  - Create `lib/sdlc_engine/rules.py`: `load()`, `CLASSES`, `ALLOWABLE = {"heuristic"}`, `why(id)` with near
    matches (`difflib.get_close_matches`).
  - Modify `cli.py`: add `cmd_why` and `COMMANDS["why"]`, and update USAGE.
  - Files: `defaults/rules`, `defaults/rules.md`, `lib/sdlc_engine/rules.py` (create); `lib/sdlc_engine/cli.py`
    (modify).
  - Test first: `tests/test_rules.py` → `Registry::test_well_formed` (unique ids, a valid class and area, a
    `rules.md` section per id), `Why::test_known_id`, `Why::test_unknown_id_near_matches`. They fail because the
    module and the command don't exist.
  - Covers: AC-17, AC-22
- [x] **S2**: Ids in the Python guards.
  - `guards._block(id, reason, procedure)` emits `BLOCKED [<id>] by zouj-ai-sdlc: …\nProcedure: … (sdlc why <id>)`,
    and every call site passes its specific id.
  - `secret_scan.main` emits `BLOCKED [G-SEC-…] by guard-…`.
  - `cli.hook`'s fail-closed message gets `G-FAIL-…`.
  - Files: `lib/sdlc_engine/guards.py`, `lib/sdlc_engine/secret_scan.py`, `lib/sdlc_engine/cli.py` (modify);
    `tests/test_guards.py` (modify).
  - Test first: `tests/test_guards.py::Ids::test_python_blocks_carry_registered_id`. It drives one representative
    command per rule (lock, gate, artifacts, toolchain, protected, merge, scaffold, nested) and asserts
    `BLOCKED \[G-[A-Z]+-\d\d\]` with the expected id and a `Procedure:`. It fails on today's `(read-only lock)`
    labels.
  - Covers: AC-16
- [x] **S3**: Ids in the bash hooks.
  - `block()` in `guard-bash.sh`, `guard-files.sh`, `guard-read.sh`, `guard-deploy.sh` and `guard-tests.sh` takes
    the id first and prints `BLOCKED [<id>] by <hook>: …`.
  - `lib.sh` `fail_closed`/`secret_scan`, `engine.sh` and `stop-verify.sh` get ids too.
  - Regexes stay in variables.
  - Files: `hooks/guard-bash.sh`, `hooks/guard-files.sh`, `hooks/guard-read.sh`, `hooks/guard-deploy.sh`,
    `hooks/guard-tests.sh`, `hooks/lib.sh`, `hooks/engine.sh`, `hooks/stop-verify.sh` (modify);
    `tests/test_shell_hooks.py` (modify).
  - Test first: `tests/test_shell_hooks.py::Ids::test_each_hook_block_carries_registered_id`. It covers one block
    per bash rule (force push, push to main, history, bypass, pipe-sh, credential print, env dump, system, gate,
    test lock, protected and secret file, plugin path, toolchain, credential content, read secret, prod deploy, MCP
    prod, engine failure). It fails on today's `BLOCKED by guard-…:` prefix.
  - Covers: AC-16
- [x] **S4**: Registry ↔ sources coverage.
  - Every id literal in `hooks/*.sh` and `lib/sdlc_engine/*.py` must be in `defaults/rules`, and every non-retired
    registry id must appear in at least one source.
  - Fix any gap found.
  - Files: `tests/test_rules.py` (modify); `defaults/rules` (modify if gaps).
  - Test first: `tests/test_rules.py::Coverage::test_sources_and_registry_agree`. It scans with
    `re.findall(r"G-[A-Z]+-\d\d")`. It's red if S1 registered an id that S2/S3 didn't emit, or the other way round.
  - Covers: AC-16, AC-22
- [x] **S4b**: Ship PR 1 (S1-S4).
  - Cut `feat/0004-rule-ids` from this branch at S4, with `make check` green.
  - Run a fresh-context review (the `review` skill's reviewer agents) of `main...feat/0004-rule-ids`, and put the
    findings and the verdict in the PR description.
  - Push and open PR 1 with `gh pr create`. The human merges it.
  - Then rebase `feat/0004-safe-lifecycle` on main.
  - No code changes. If the review asks for changes, fix them on `feat/0004-rule-ids` and log them in the Deviation
    log.
  - Files: none (git and the PR only).
  - Test first: not applicable (a release step). The proof is `make check` green on the PR 1 head and the
    `aiops-gates` and CI checks on the PR.
  - Covers: AC-16, AC-17, AC-22 (shipped)
- [x] **S5**: The allowance in the Python guard.
  - `rules.allowed(root, id, command)`: reads `.aiops/config/allowed-commands`. True only if the id's class is in
    `ALLOWABLE`, the command is single-line, and an entry is byte-equal to `command.strip()`.
  - `rules.allowance_problems(text)`: unknown id, non-allowable class, multi-line, malformed.
  - `check_bash`: the nested-shell rule (the only Python heuristic) consults `allowed` with the raw top-level
    command and continues instead of blocking.
  - Files: `lib/sdlc_engine/rules.py`, `lib/sdlc_engine/guards.py` (modify).
  - Test first: `tests/test_rules.py::Allowance` with these cases:
    - exact match allows
    - an extra space, a `; …` suffix, or a different id doesn't
    - a gate-class id is never allowed
    - problems listed per class

    They fail because `allowed` doesn't exist.
  - Covers: AC-18, AC-19
- [x] **S6**: The allowance in `guard-bash.sh`.
  - A `heuristic <id> <regex-var> <reason> [procedure]` helper. On a match, it checks the registry class
    (`grep -F` on `$PLUGIN_ROOT/defaults/rules`), and an exact `<id> <command>` line in
    `$root/.aiops/config/allowed-commands`, compared as a fixed string with `grep -Fxq`. It's honoured only when
    `aiops_enabled`. Otherwise it blocks.
  - `re_rm_root`, `re_dump_env`, `re_system` and `re_pipe_sh` go through the helper. Every other rule calls
    `block` directly, so a gate rule can never reach the allowance code.
  - Files: `hooks/guard-bash.sh`, `hooks/lib.sh` (modify).
  - Test first: `tests/test_shell_hooks.py::Allowance` with these cases:
    - `ls env` with an entry for its `G-ENV` id is allowed
    - `ls env; git push --force` is blocked (force push)
    - `ls  env x` is blocked
    - an entry `<push-main id> git push origin main` is still blocked
    - an entry for a secret-read id is still blocked
    - no `.aiops/` means no allowance

    They fail because there's no helper yet.
  - Covers: AC-18, AC-19
- [x] **S7**: Allowance audit in doctor and CI.
  - `cmd_doctor`: a `✗` row per `allowance_problems` entry, naming the id's class.
  - `cmd_validate --ci`: reads `allowed-commands` from `--base` (else the work tree) and adds the problems to the
    errors.
  - Files: `lib/sdlc_engine/cli.py` (modify).
  - Test first: `tests/test_cli.py::Allowances::test_doctor_flags_gate_entry` and
    `::test_validate_ci_fails_on_base_entry`. The second commits a gate-id entry on a base branch and runs
    `validate --ci --base <it>`. Both fail because neither command reads the file today.
  - Covers: AC-19
- [x] **S8**: Install-state written by init and setup, and guarded.
  - `lib/sdlc_engine/lifecycle.py`:
    - `STATE = ".aiops/install-state.json"`
    - `load` / `save` (via `write_file`, repo-relative paths only)
    - `sha256_file`
    - `render(rel, ref)`
    - `record(root, paths, profile, stack, ref)`
  - `cmd_init` and `setup.apply` call `record` after the writes (config merge and stack wiring included), so the
    hashes are of the bytes on disk.
  - `defaults/protected-paths` adds `.aiops/install-state.json engine-written; changed only by sdlc
    init/setup/upgrade/repair/uninstall`.
  - The scaffold CODEOWNERS adds `/.aiops/install-state.json`.
  - Files: `lib/sdlc_engine/lifecycle.py` (create); `lib/sdlc_engine/cli.py`, `lib/sdlc_engine/setup.py`,
    `defaults/protected-paths`, `templates/scaffold/.github/CODEOWNERS` (modify).
  - Test first: `tests/test_lifecycle.py::InstallState::test_init_records_every_file` (the version, ref
    `v<version>`, profile, stack, a sha per written file equal to the file on disk, no absolute paths) and
    `::test_setup_records_profile_and_stack`. Also `tests/test_guards.py::InstallState::test_agent_cannot_write_it`
    (Edit, Write and `echo > .aiops/install-state.json` are each blocked with a `G-FILE`/`G-ART` id). They fail
    because nothing writes the file and the path isn't protected.
  - Covers: AC-1, AC-15
- [x] **S9**: `sdlc list-installed`.
  - `lifecycle.classify(root, state)` → `{rel: current|stale|modified|missing|unmanaged}`. `stale` compares with
    `render(rel, state.ref)` of the running template.
  - `cmd_list_installed` prints the header and the rows, and writes nothing.
  - With no install-state, it prints the adoption preview (S10) and the command to adopt.
  - Files: `lib/sdlc_engine/lifecycle.py`, `lib/sdlc_engine/cli.py` (modify).
  - Test first: `tests/test_lifecycle.py::ListInstalled::test_statuses_and_no_writes`. Edit one file, delete
    another, and assert `modified`/`missing`/`current`, plus `git status --porcelain` unchanged before and after.
    It fails because the command doesn't exist.
  - Covers: AC-2
- [x] **S10**: Scaffold history and adoption.
  - `scripts/scaffold-history.py` (stdlib): for each `v*` tag, `git ls-tree`/`git show` the `templates/scaffold/`
    files, normalise `ZOUJ_SDLC_REF:`/`"ref":` values back to `__ZOUJ_SDLC_REF__`, and hash them. It adds the
    working-tree scaffold under the current `plugin.json` version.
  - Generate `defaults/scaffold-history.json`.
  - `lifecycle.normalize(rel, data)`, and `lifecycle.adopt(root)`: a file matching a history hash (Makefiles are
    also tried with each stack preset applied through the pure `wire()`) becomes managed at that version. The rest
    are `modified` or `unmanaged`, and only install-state is written.
  - `cli._wire_stack` is split into the pure `wire(src, stack)` plus the write.
  - Files: `scripts/scaffold-history.py`, `defaults/scaffold-history.json` (create); `lib/sdlc_engine/lifecycle.py`,
    `lib/sdlc_engine/cli.py` (modify).
  - Test first, all failing because there's no history file or `adopt`:
    - `tests/test_lifecycle.py::Adoption::test_alpha1_and_alpha2_repos_adopted`: builds a repo from
      `git archive v0.2.0-alpha.1` (and alpha.2) of `templates/scaffold/` with the ref substituted. Edits one file.
      Asserts managed vs modified, and that only install-state was written.
    - `::test_stack_wired_makefile_matches`.
    - `tests/test_rules.py::History::test_current_scaffold_in_history` (AC-22).
  - Covers: AC-8, AC-22
- [x] **S11**: `sdlc repair [--dry-run] [--yes]`.
  - `plan_repair` re-creates `missing` managed files only.
  - Under the agent, human-owned paths are skipped and printed with the human's terminal command.
  - One confirmation (`--yes`; no terminal → exit 2, nothing written).
  - Adopts first when there's no install-state.
  - Updates install-state.
  - Files: `lib/sdlc_engine/lifecycle.py`, `lib/sdlc_engine/cli.py` (modify).
  - Test first, all failing because the command doesn't exist:
    - `tests/test_lifecycle.py::Repair::test_restores_missing_keeps_modified`
    - `::test_dry_run_and_no_tty_write_nothing`
    - `::test_agent_skips_human_owned` (`CLAUDECODE=1`, a deleted `.github/workflows/ci.yml` isn't restored and is
      printed)
  - Covers: AC-3, AC-6
- [x] **S12**: Ref resolution.
  - `lifecycle.resolve_ref(plugin_root, home)`, in order:
    1. `installed_plugins.json` (any entry whose `installPath` resolves to `plugin_root` →
       `gitCommitSha`, validated as 40 hex)
    2. a git checkout's HEAD, if `git branch -r --contains HEAD` is non-empty
    3. `v<version>` plus a warning
  - `home` is injectable for tests.
  - Files: `lib/sdlc_engine/lifecycle.py` (modify).
  - Test first: `tests/test_lifecycle.py::Ref` with these cases:
    - an installed_plugins entry wins
    - a malformed sha is ignored
    - a checkout reachable from a remote-tracking ref gives HEAD
    - an unpushed HEAD falls back to the tag with a warning

    They fail because there's no function yet.
  - Covers: AC-9
- [x] **S13**: Migrations and `sdlc upgrade [--dry-run] [--yes]`.
  - `lib/sdlc_engine/migrations.py`: `Migration(id, applies, human_only, command)` and `MIGRATIONS =
    [legacy_approvals]`.
  - `plan_upgrade`: adopt if needed, then:
    - `stale` → replace (show the diff)
    - `missing` and new template files → create
    - `modified` → keep, and print the old→new template diff
    - removed template files → list
    - set the ref value in every file that holds one, as a single-value rewrite in modified files

    Pending migrations are listed. A `human_only` one is printed and never run.
  - Under the agent, human-owned paths are skipped and recorded at their old version.
  - "Already at <version>" when nothing changes.
  - One confirmation. Updates install-state.
  - Files: `lib/sdlc_engine/migrations.py` (create); `lib/sdlc_engine/lifecycle.py`, `lib/sdlc_engine/cli.py`
    (modify).
  - Test first: `tests/test_lifecycle.py::Upgrade`, failing because the command doesn't exist. Its fixture: an
    install-state at an older version, with an older template for file A (written into a temp copy of the scaffold
    via a monkeypatched `TEMPLATES`) and a user edit in file B.
    - `test_replaces_stale_keeps_modified_bumps_ref`
    - `test_second_run_is_noop`
    - `test_dry_run_and_no_tty_write_nothing`
    - `test_agent_never_writes_human_owned`
    - `test_legacy_approvals_listed_never_run`
  - Covers: AC-4, AC-5, AC-6, AC-7, AC-10
- [x] **S14**: `sdlc uninstall [--dry-run] [--yes]`.
  - `plan_uninstall` removes a path only if it's recorded, in some version's `scaffold-history.json`, and equal to
    its recorded hash. It never touches `.aiops/NNNN-*`, `.aiops/state/` or `.aiops/` itself.
  - Last, it removes install-state and the `.gitignore` lines `init` added.
  - The real run is refused under the agent with `HUMAN_ONLY`. `--dry-run` writes nothing.
  - Removal uses `os.unlink` with `dir_fd`/no-follow, like `write_file`.
  - Files: `lib/sdlc_engine/lifecycle.py`, `lib/sdlc_engine/cli.py` (modify).
  - Test first, all failing because the command doesn't exist:
    - `tests/test_lifecycle.py::Uninstall::test_removes_only_unmodified_managed` (intent folders, `.aiops/state`, a
      modified file and a non-scaffold file remain)
    - `::test_tampered_state_refused` (`src/app.py`, `.aiops/0001-x/intent.md`)
    - `::test_agent_refused_dry_run_allowed`
  - Covers: AC-11, AC-12, AC-13
- [x] **S15**: Guard extensions for the new commands.
  - `SCAFFOLD_RE` covers `init|setup|upgrade|repair|uninstall`, so they run only in the session's repo (cd, `-C`,
    `GIT_*` refused).
  - `ENGINE_RES` blocks `sdlc uninstall` unless the same command word list contains `--dry-run`.
  - Update `architecture.md`'s threat-model rows in S18.
  - Files: `lib/sdlc_engine/guards.py` (modify).
  - Test first: `tests/test_guards.py::Lifecycle` with these cases:
    - `sdlc uninstall` is blocked (`G-GATE`), and `sdlc uninstall --dry-run` is allowed
    - `cd ../other && sdlc upgrade` and `GIT_DIR=x sdlc repair` are blocked (`G-SCAF`)
    - `sdlc upgrade` in the session repo is allowed

    They fail because today's regexes don't name the new commands.
  - Covers: AC-13, AC-15
- [x] **S16**: Playbook conformance and the round trip.
  - `test_playbook.Playbook._walk` gains these checks at states 1-5:
    - `upgrade --yes` and `repair --yes` (agent env) leave gates, `sdlc status`, the artifacts and the lock
      unchanged
    - an `allowed-commands` entry for the push-to-main id and the `.aiops` write id is still blocked
  - A new round-trip test, `init → upgrade → uninstall --dry-run`: git status shows only managed paths and
    install-state.
  - An alpha.2-shaped repo (no install-state) passes status, hooks and walk unchanged.
  - The checks are factored into `playbook_violations(root, before) -> [str]`. It compares a snapshot taken before
    the command with the state after it:
    - every gate's state (`sdlc status --json`)
    - the artifact files and their front matter
    - whether the read-only lock holds (an Edit of a code file in state 1-3 is still blocked)
    - no code file changed while the lock was on
  - **Permanent test that breaks `upgrade` on purpose:**
    `tests/test_playbook.py::Mutation::test_conformance_catches_broken_upgrade`. It runs `sdlc upgrade --yes`
    in-process (`cli.main`) with `lifecycle.apply_upgrade` wrapped by `unittest.mock.patch`, so it calls the real
    function and then breaks the playbook. There are three subtests, one per break:
    - (a) stamps `status: Approved` + `approved-sha256` into the Draft plan.md (opens a gate)
    - (b) deletes `intent.md` (removes an artifact)
    - (c) writes `src/app.py` in state 1 (code under the lock)

    Each asserts `playbook_violations` is non-empty and names the break. A control run without the patch asserts it
    is empty. No test hook goes into production code.
  - Files: `tests/test_playbook.py`, `tests/test_lifecycle.py` (modify).
  - Test first: write `playbook_violations` as a stub that returns `[]`, with `Mutation` and the new walk
    assertions. The three subtests that break `upgrade` are red against the stub, which is the Red evidence. Then
    implement the checker. The control run and the walk turn green, and the subtests pass because they're caught.
    `RoundTrip::test_init_upgrade_uninstall_dry_run` and `Compat::test_alpha2_repo_unchanged` are added in the same
    step.
  - Covers: AC-14, AC-20, AC-21
- [x] **S17**: The `/zouj-ai-sdlc:configure` skill.
  - It runs `sdlc list-installed`, `sdlc doctor` and `sdlc setup --dry-run --profile <choice>`, then gives the
    human the terminal command `<python> -I <plugin>/bin/sdlc setup --profile <choice>`. No writes.
  - `skills/setup` and `skills/status` mention `list-installed`, `upgrade` and `why`.
  - The README's skill list is updated.
  - Files: `skills/configure/SKILL.md` (create); `skills/setup/SKILL.md`, `skills/status/SKILL.md` (modify).
  - Test first: `tests/test_rules.py::Skills::test_configure_is_read_only`. The skill exists, its body names only
    `list-installed`, `doctor` and `setup --dry-run` as commands it runs, and it ends with the human's terminal
    command. It fails because the file is missing. `make validate` passes.
  - Covers: AC-23
- [ ] **S18**: Docs and release prep.
  - README: a Lifecycle section (list-installed, repair, upgrade, uninstall, why, allowances).
  - `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md` ("Blocked? → `sdlc why <id>`; false positive → allowance, if
    heuristic").
  - `docs/architecture.md`: threat-model rows for install-state, uninstall, allowances and the agent's
    upgrade/repair, plus layout lines for `lifecycle.py`, `rules.py` and `migrations.py`.
  - `docs/adr/0002-allowances-never-touch-a-gate.md`.
  - `docs/roadmap.md`: Phase 2 status.
  - CHANGELOG `[0.2.0-alpha.3]`.
  - Version bump to `0.2.0-alpha.3` in `.claude-plugin/plugin.json` and `marketplace.json`, then regenerate
    `scaffold-history.json` for it.
  - Files: `README.md`, `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md`, `docs/architecture.md`,
    `docs/roadmap.md`, `CHANGELOG.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
    `defaults/scaffold-history.json` (modify); `docs/adr/0002-allowances-never-touch-a-gate.md` (create).
  - Test first: `tests/test_rules.py::History::test_current_scaffold_in_history` turns red at the version bump
    until the history is regenerated. `tests/test_cli.py::Init::test_scaffold_pins_and_protects` still passes.
  - Covers: AC-22

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Re-prefixing every block message breaks a test or doc that matches the old text | high | low | S2/S3 change messages and their tests in the same commit; the new prefix keeps `BLOCKED` and `by <hook>`; only 2 docs/tests grep `BLOCKED by` today |
| An allowance lifts more than intended (compound command, whitespace tricks, gate rule) | medium | high | only `heuristic` ids reach the allowance code (gate rules call `block` directly); `grep -Fxq` exact line; all other rules still evaluated; S6/S16 negative tests; doctor and CI audit from base |
| Uninstall deletes something it shouldn't | low | high | triple condition (recorded ∧ in scaffold history ∧ unmodified), never `.aiops/NNNN-*`/`state`; human-only in CLI and guard; dry-run first; S14 tampered-state test |
| Upgrade under the agent rewrites the CI audit or settings | low | high | human-owned paths skipped under `running_under_agent()`; S13 test; CI reads config and engine from base anyway |
| `scaffold-history.json` drifts from the scaffold | medium | medium | generated by a script; `make check` test fails when the current scaffold isn't in it (S10/S18) |
| `installed_plugins.json` format changes in a Claude Code update | medium | low | parse defensively; any failure falls back to the checkout HEAD, then the tag with a warning (S12) |
| Rewriting only the ref in a modified workflow corrupts the file | low | medium | one anchored regex per known line shape (`ZOUJ_SDLC_REF: `, `"ref": "`); file left unchanged if no match; shown in the diff before confirmation |
| Registry coverage test is brittle (ids in comments, retired ids) | medium | low | `retired` marker in `defaults/rules`; scan only `block`/`_block`/`heuristic` call lines |
| The conformance checker passes because it checks too little | medium | high | permanent test that breaks `upgrade` on purpose (S16): three planted breaks must each be reported, and a clean control run must report none |
| PR 1 merges, but PR 2 stalls, leaving ids without allowances | low | low | PR 1 is self-contained (no behaviour change, `sdlc why` works); the intent stays in EXECUTION on main until PR 2 |
| Hook latency on every call | low | medium | registry/allowance only read on the block path; no new work on allowed calls |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_lifecycle.py::InstallState::test_init_records_every_file` | integration | init writes install-state with version, ref, profile, stack, per-file sha of bytes on disk, repo-relative paths only |
| AC-2 | `tests/test_lifecycle.py::ListInstalled::test_statuses_and_no_writes` | integration | modified/missing/current reported, work tree unchanged |
| AC-3 | `tests/test_lifecycle.py::Repair::test_restores_missing_keeps_modified` | integration | missing restored byte-equal, modified untouched, state updated |
| AC-4 | `tests/test_lifecycle.py::Upgrade::test_replaces_stale_keeps_modified_bumps_ref` | integration | stale replaced with diff, modified kept but for the ref line, all refs = resolved ref, new version recorded |
| AC-5 | `tests/test_lifecycle.py::Upgrade::test_second_run_is_noop` | integration | "Already at <version>", no writes |
| AC-6 | `tests/test_lifecycle.py::Upgrade::test_dry_run_and_no_tty_write_nothing`, `::Repair::test_dry_run_and_no_tty_write_nothing` | integration | dry-run exit 0 / no tty exit 2, tree unchanged, plan printed |
| AC-7 | `tests/test_lifecycle.py::Upgrade::test_agent_never_writes_human_owned` | integration | under `CLAUDECODE=1` no human-owned path changes; printed with the human command; recorded at old version |
| AC-8 | `tests/test_lifecycle.py::Adoption::test_alpha1_and_alpha2_repos_adopted`, `::test_stack_wired_makefile_matches` | integration | history hashes adopt unmodified files; edited ones `modified`; only install-state written |
| AC-9 | `tests/test_lifecycle.py::Ref::test_installed_plugins_sha`, `::test_checkout_head_reachable`, `::test_fallback_tag_warns` | unit | resolution order and fallback warning |
| AC-10 | `tests/test_lifecycle.py::Upgrade::test_legacy_approvals_listed_never_run` | integration | human-only migration printed, never executed, not recorded while pending |
| AC-11 | `tests/test_lifecycle.py::Uninstall::test_removes_only_unmodified_managed` | integration | only unmodified managed files + install-state removed; artifacts, state, modified, non-scaffold kept |
| AC-12 | `tests/test_lifecycle.py::Uninstall::test_tampered_state_refused` | integration | tampered paths (code, artifact) not removed, reported |
| AC-13 | `tests/test_lifecycle.py::Uninstall::test_agent_refused_dry_run_allowed`, `tests/test_guards.py::Lifecycle::test_uninstall_human_only` | integration | CLI refuses agent, dry-run allowed; guard blocks `sdlc uninstall`, allows `--dry-run` |
| AC-14 | `tests/test_lifecycle.py::RoundTrip::test_init_upgrade_uninstall_dry_run` | integration | only managed paths and install-state touched across the round trip |
| AC-15 | `tests/test_guards.py::InstallState::test_agent_cannot_write_it`, `tests/test_guards.py::Lifecycle::test_other_repo_refused` | unit | Edit/Write/redirect to install-state blocked with id; upgrade/repair elsewhere blocked `G-SCAF` |
| AC-16 | `tests/test_guards.py::Ids::test_python_blocks_carry_registered_id`, `tests/test_shell_hooks.py::Ids::test_each_hook_block_carries_registered_id`, `tests/test_rules.py::Coverage::test_sources_and_registry_agree` | unit | every block site emits a registered id and a Procedure; every registry id is emitted |
| AC-17 | `tests/test_rules.py::Why::test_known_id`, `::test_unknown_id_near_matches` | unit | `sdlc why` prints summary/class/stage/alternative/allowability; unknown → exit 1 with near matches |
| AC-18 | `tests/test_rules.py::Allowance::test_exact_match_only`, `tests/test_shell_hooks.py::Allowance::test_heuristic_exact_command` | unit | exact entry allows only that command and that rule; compound, whitespace variants and other ids still blocked |
| AC-19 | `tests/test_shell_hooks.py::Allowance::test_gate_and_secret_entries_ignored`, `tests/test_cli.py::Allowances::test_doctor_flags_gate_entry`, `::test_validate_ci_fails_on_base_entry` | integration | gate/secret/toolchain/safety entries never allow; doctor ✗ with class; `validate --ci --base` fails |
| AC-20 | `tests/test_playbook.py::Playbook::test_solo`, `::test_team`, `::test_strict`, `tests/test_playbook.py::Mutation::test_conformance_catches_broken_upgrade` | e2e | walk passes per profile; gate allowance rejected; upgrade/repair mid-walk leave gates, lock and artifacts unchanged; the conformance checker catches an upgrade that opens a gate, deletes an artifact or writes code under the lock |
| AC-21 | `tests/test_lifecycle.py::Compat::test_alpha2_repo_unchanged` + the existing suite | integration | an alpha.2-shaped repo with no install-state works unchanged |
| AC-22 | `tests/test_rules.py::Registry::test_well_formed`, `tests/test_rules.py::History::test_current_scaffold_in_history` | unit | `make check` fails on a malformed or duplicate registry line or a missing scaffold history entry |
| AC-23 | `tests/test_rules.py::Skills::test_configure_is_read_only` + `make validate` | unit | the configure skill runs only read-only commands and `setup --dry-run`, then hands the human the command; plugin validates |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-06 | S1 | **Allowable set narrowed:** only G-BASH-07 and G-ENV-03 are `heuristic`. G-BASH-01, G-BASH-02 and G-BASH-06 are now `safety`. This supersedes the list in Approach. | PR 1 security review: each of these three stands in front of every other check, so an allowance would lift all of them. Decided by zoujagger, 2026-11-06. | PR 1 review fixes |
| 2026-11-06 | S1/S3 | **New rule G-ENV-04** (`secret`): the `echo $…KEY/TOKEN/SECRET/PASSWORD` branch is split out of `re_dump_env` (G-ENV-03). Both forms still block. | Both reviews: credential printing must never be allowable (spec flag). Decided by zoujagger, 2026-11-06. | PR 1 review fixes |
| 2026-11-06 | S1 | **New stage `initialized-repo`**, and `sdlc why` prints every stage in words. rules.md and `why` don't mention allowances or upgrade, repair or uninstall until that code exists; S5 and S15 add that text back. | Code review MEDIUM 2/3: `why` overstated scope and described features PR 1 doesn't ship. | PR 1 review fixes |
| 2026-11-06 | S2 | Not in S2's text: a protected-path shell write (G-FILE-01) is told apart from a secret one (G-SEC-02, with its own wording). The post-edit schema check gets G-ART-09 and reads `NOT VALID … was saved`, not `BLOCKED`. | Ids must name one rule each. The PostToolUse edit has already landed (code review LOW 1, MEDIUM 1). | cb25f89, PR 1 review fixes |
| 2026-11-06 | S4 | The Ids tests drive every registered id that can be reached (G-FAIL-01 crash, G-FAIL-03 scan failure), and hook procedures match `sdlc why`. | Code review MEDIUM 4, LOW 3. | PR 1 review fixes |
| 2026-11-06 | — | Out of scope, recorded for intent 0005: in states 4-5 the shell-write check allows `rm -rf ./`, `"$PWD"`, `.github/workflows` and `mv .github …`, because protected paths are matched exactly, not as parent directories. This is already on main. | Security review (pre-existing). Decided by zoujagger: a new intent 0005, after 0004. | — |
| 2026-11-06 | — | Also recorded for intent 0005, and also already on main: in a repo *without* `.aiops/`, shell writes to the toolchain (`~/.gitconfig`, `~/.bashrc`, `git config --global gpg.ssh.program`), to the installed plugin and to secrets outside the repo (`~/.ssh/…`) aren't checked (`check_bash` returns early). G-TOOL-04's `every-repo` label is only true for Edit/Write. `docs/architecture.md` is corrected to say so. | Security re-review (pre-existing). Grouped with the `rm` gap under 0005, following zoujagger's decision. | PR 1 review fixes |
| 2026-11-06 | S3 | G-ENV-04 is checked before G-ENV-03, so a command matching both reports the id that can't be allowed. | Security re-review LOW. | PR 1 review fixes |
| 2026-11-06 | S5 | `guards.py` isn't changed: no Python rule is allowable any more (G-BASH-01 became `safety`), so S5 ships only `rules.allowed` and `rules.allowance_problems`. `allowed` also refuses a command with any control character but tab (for example `\r`), not only multi-line ones. | Follows the PR 1 class decision. A `\r` would make a different command look identical. | S5 |
| 2026-11-06 | S6 | The `heuristic` helper doesn't parse `allowed-commands` with `grep` in bash. It calls `rules.allowed` through `python3 -I`, only on the block path. Only G-BASH-07 and G-ENV-03 go through it, after the PR 1 class decision. `sdlc why` now describes the allowance line. | One definition of an exact match, the same in the hook, doctor and CI. If python3 can't run, the command stays blocked. | S6 |
| 2026-11-06 | S7 | `validate --ci` checks `allowed-commands` in the change itself as well as on `--base` (the spec names only the base). | A PR that adds a bad entry fails CI before it merges, not only afterwards. Stricter, no new trust. | S7 |
| 2026-11-06 | S8 | `init` and `setup` record only the files they wrote. Kept files are claimed later by adoption (S10, R-5). `.gitignore` is never recorded. `.aiops/install-state.json` is also in `guards.GUARDED_RE`, so `check_edit` blocks it (G-ART-01) as well as `protected-paths` (G-FILE-*). Nothing is written when nothing was, so a rerun leaves the state unchanged. | R-1's matching of kept files needs S10's history; two guard layers instead of one. | S8 |
| 2026-11-06 | S9 | Two more statuses than R-2 lists: `dropped` (recorded, no longer in the plugin's scaffold) and `new` (in the scaffold, never installed). `stale` is decided from the entry's version and the running template, since the old template isn't known until S10's history. S10's split of `_wire_stack` into a pure `cli.wire()` is done here. Without install-state, the command lists files on disk as `unmanaged`; S10 adds the adoption preview. | R-4 needs both extra cases named. A stack-wired Makefile would otherwise always look stale. | S9 |
| 2026-11-06 | S10 | The history files today's scaffold under `unreleased` while `plugin.json` still says the tagged `0.2.0-alpha.2`; S18's bump turns it into `0.2.0-alpha.3`. `adopt()` writes nothing: S11/S13 save its result. `list-installed` shows it as a preview. A file that differs from every release is recorded with `sha256: null` (so `modified`). Where several releases match, the version comes from the file's pinned ref, else the newest. The adoption tests read alpha.1 and alpha.2 by commit (`429614a`, `0f8d4f6`), not by tag, because `v0.2.0-alpha.2` exists only locally until the release. `cli.wire()` takes a release's recipes. | No version bump before S18's CHANGELOG (a test pins the two together). CI must not depend on a local tag. | S10 |
| 2026-11-06 | S11 | Run by the agent, `repair` skips every path the agent couldn't write itself (`cli._agent_blocked`: protected paths and code under the read-only lock), not only human-owned ones, and hands them to the human. A missing file recorded at an older version is restored from the running template, with the recorded ref. The plan, confirm and apply helpers are shared with `upgrade` and `uninstall`. | A lifecycle command must not weaken the read-only lock (intent). The old template's bytes aren't shipped, only its hash. | S11 |
| 2026-11-06 | S13 | `.aiops/config.json` and `.claude/settings.json`, which setup merges keys into, are never replaced, only ref-pinned. Their record follows the pin when it still matched. For a modified file, the diff shown is between the file and the new template, not old template vs new: only the old template's hash is shipped. Run by the agent, upgrade keeps the old `ref` in install-state until the human has written the human-owned files. A failed `--base` resolution counts as "no legacy approvals pending". | Replacing a merged config would drop the profile. The old template's bytes aren't in the plugin. | S13 |
| 2026-11-06 | S14 | `uninstall` leaves directories that end up empty in place, and deletes `.gitignore` only if nothing else is left in it. A path in install-state is refused before it is ever read when it isn't a scaffold path (`../outside.txt` included). Install-state itself is never on the removal list; it's removed last. | Removing directories is a separate decision, and git doesn't track empty ones anyway. Reading a tampered path is a risk in itself. | S14 |
| 2026-11-06 | S16 | The test that breaks upgrade on purpose wraps `lifecycle.save`, the last act of `cmd_upgrade`, because there's no `apply_upgrade` to patch. The "opens a gate" break stamps the Draft `intent.md` in state 1, not `plan.md` in state 3, because one fixture serves all three breaks. `playbook_violations` and `snapshot` live in `tests/test_playbook.py`. The walk also checks that `doctor` reports a gate-id allowance. | Same proof, one fixture. The checker is test code, not engine code. | S16 |
| 2026-11-06 | S4b | PR 1 is #11, merged by zoujagger as 267f34a. Review: code PASS 93/100 after one CHANGES_REQUESTED round, security PASS 23/25 (0 decision differences from main). S5-S7 were built on the PR 1 branch while it waited, then rebased onto main. | PR 1 sat open after CI passed. | 267f34a |
