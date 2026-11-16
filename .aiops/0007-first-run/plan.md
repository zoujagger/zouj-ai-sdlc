---
id: 0007
title: First run in five minutes (profile by /setup, terminal command, core scaffold)
status: Approved
spec: ./spec.md
created: 2026-11-10
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-13T11:20:14Z
approved-via: prompt
approved-sha256: 0942404d231de13a599a22e745f5be4b77808f057d28539bd7007864a4f3aaf7
---

# Plan: First run in five minutes (profile by /setup, terminal command, core scaffold)

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Three engine changes, then text, then the release. The scaffold work goes first because it changes a default that
many tests rely on; the phrase builds on a scaffolded repo; the version bump is last so the pins move once.

1. **Parts (S1-S4).** A manifest, then `init`, `setup` and the lifecycle commands read the installed parts from one
   function. Reused: `cli.init_actions` (`lib/sdlc_engine/cli.py:436`), `lifecycle.record`, `scaffold_paths` and
   `classify` (`lib/sdlc_engine/lifecycle.py:54`, `:83`, `:96`), `setup.parse` (`lib/sdlc_engine/setup.py:317`).
2. **Profile by phrase (S5-S7).** `setup.set_first_profile`, then the prompt hook, then the playbook walk driven by
   the phrase. Reused: `setup.PROFILE_CONFIG`, `_as_setup_writes` and `human_steps` (`setup.py:157`, `:219`, `:462`),
   `approvals._commit_alone` (`lib/sdlc_engine/approvals.py:133`), `cli.hook_prompt` (`cli.py:747`).
3. **`sdlc where` and the card (S8).** Over `lifecycle.human_command` (`lifecycle.py:257`).
4. **Scaffold text and skills (S9-S10), the eval (S11), docs (S12),** then **the release (S13).**
5. **Amendment (S14-S20, spec amended 2026-11-13).** The typed `/zouj-ai-sdlc:setup <profile>` replaces the
   `Setup Profile` phrase, and in a repo without `.aiops/` the hook writes the core scaffold first. Order: the
   dormancy exception in `hooks/engine.sh` (S14), the command in the prompt hook (S15), the fresh-repo scaffold
   (S16), the playbook walk and the card (S17), then skills (S18), the eval (S19) and docs (S20). Reused:
   `setup.preflight`, `setup.plan`, `setup.apply`'s create path, `cli.scaffold_root_problem`,
   `setup.steps_for_human`, `approvals._commit_alone`. S1-S13 stay ticked; S5-S7 and S10-S12 are reworked by
   S15-S20, and the tests named there are renamed where they name the phrase.

What the existing tests need:
- `tests/helpers.py::RepoCase` creates `.aiops/` by hand with an edited `config.json` and no install-state before
  `sdlc init`, so it keeps getting every part (spec R-13). Tests built on it stay as they are.
- Tests that set up a fresh repo (`tests/test_setup.py::SetupCase`, `tests/test_playbook.py::Playbook.repo`) and
  expect the full scaffold pass `--with all` in the step that changes the default.
- `lifecycle.scaffold_paths()` with no argument keeps returning every path (`tests/test_rules.py::History` and
  `scripts/scaffold-history.py` use it).

The spec's open question is answered. zoujagger's probe (2026-11-10) showed that a UserPromptSubmit hook in a session
started from a terminal sees `CLAUDECODE=1` and `CLAUDE_CODE_CHILD_SESSION=1`, the same as in a session the agent
starts. The hook path therefore reads no marker (spec R-2, AC-6), and the nested-session exposure is recorded as a
known gap in S12.

## Steps
- [x] **S1**: Add the parts manifest and its reader.
  - Files: `defaults/scaffold-parts` (create), `lib/sdlc_engine/lifecycle.py` (modify: `PARTS`, `parts()`,
    `part_of(rel)`, `parse_parts(value)`)
  - Test first: `tests/test_lifecycle.py::Parts::test_every_scaffold_file_has_one_part`,
    `::test_every_manifest_line_matches_a_file`, `::test_never_declined_is_core`, `::test_core_is_sixteen_files` →
    fail: no manifest, no `parts()`
  - Covers: AC-15
- [x] **S2**: `sdlc init` installs the chosen parts and records them.
  - Files: `lib/sdlc_engine/lifecycle.py` (modify: `installed_parts(root, st, requested)`, `scaffold_paths(parts=None)`,
    `record(..., parts=)` writes `"parts"`), `lib/sdlc_engine/cli.py` (modify: `init_actions(..., parts=)`, `cmd_init`
    parses `--with`, USAGE). With nothing recorded, `installed_parts` reads the disk: template `config.json` or no
    `.aiops/` → the parts that have a file; an edited config → every part
  - Test first: `tests/test_cli.py::InitParts::test_fresh_init_writes_core`, `::test_with_adds_only_that_part`,
    `::test_with_all`, `::test_unknown_part_refused_before_writing`, `::test_rerun_without_with_keeps_parts`,
    `::test_edited_config_without_state_gets_every_part`, `::test_template_config_with_full_scaffold_gets_every_part`,
    `::test_rerun_after_partial_core_setup_stays_core`, `::test_rerun_after_partial_with_maintain_completes_it` →
    fail: `--with` is ignored and a fresh init writes 36 files
  - Covers: AC-11, AC-12, AC-14, AC-20
- [x] **S3**: `sdlc setup --with`, the preview of left-out parts, and the playbook walk on a core-only repo.
  - Files: `lib/sdlc_engine/setup.py` (modify: `OPTIONS` and `parse` accept `--with` through `parse_parts`, `plan`
    and `apply` take the parts, the dry-run names the parts left out), `tests/test_playbook.py` (modify:
    `repo(profile, parts="all")`, a `CoreWalk` class), `tests/test_setup.py` (modify: fresh-repo tests that expect
    the full scaffold pass `--with all`)
  - Test first: `tests/test_setup.py::Parts::test_default_is_core_with_no_schedule_or_secret`,
    `::test_dry_run_names_parts_left_out`, `::test_with_maintain_adds_only_maintain`, `::test_bogus_part_refused`;
    `tests/test_playbook.py::CoreWalk::test_solo`, `::test_team`, `::test_strict` → fail: unknown option `--with`
  - Covers: AC-11, AC-12, AC-16
- [x] **S4**: `list-installed`, `repair` and `upgrade` leave uninstalled parts alone.
  - Files: `lib/sdlc_engine/lifecycle.py` (modify: `classify` skips paths of parts that aren't installed unless
    recorded or on disk, `cmd_list_installed` ends with the parts line)
  - Test first: `tests/test_lifecycle.py::CoreOnly::test_list_installed_hides_parts_not_installed`,
    `::test_upgrade_and_repair_create_none_of_them`, `::test_unrecorded_part_file_on_disk_is_unmanaged`,
    `tests/test_lifecycle.py::Compat::test_state_without_parts_reads_as_every_part` → fail: the 20 opt-in files show
    as `new` and `upgrade` creates them
  - Covers: AC-13, AC-14
- [x] **S5**: `setup.set_first_profile`: check, write, commit alone, reply.
  - Files: `lib/sdlc_engine/setup.py` (modify: `template_config()` factored out of `_as_setup_writes`,
    `no_profile_yet(root)`, `set_first_profile(root, name)`)
  - Test first: `tests/test_setup.py::FirstProfile::test_sets_and_commits_config_alone`,
    `::test_staged_scaffold_stays_staged`, `::test_repo_with_no_commit_yet`, `::test_refused_when_profile_set`,
    `::test_refused_when_config_edited`, `::test_refused_when_an_artifact_is_approved_or_closed`,
    `::test_symlinked_config_refused`, `::test_commit_failure_leaves_the_change`,
    `::test_team_reply_has_signing_steps`, `::test_strict_reply_has_codeowners_step` → fail: no such function
  - Covers: AC-1, AC-3, AC-8
- [x] **S6**: The prompt hook recognises the phrase.
  - Files: `lib/sdlc_engine/cli.py` (modify: `PROFILE_RE`, `hook_prompt` tries it after `APPROVE_RE`, the
    unknown-name reply; no environment marker is read on this path)
  - Test first: `tests/test_cli.py::ProfilePhrase::test_whole_prompt_sets_the_profile`,
    `::test_phrase_inside_other_text_is_ignored`, `::test_unknown_or_missing_name_lists_profiles`,
    `::test_dormant_without_aiops`, `::test_works_with_the_session_markers_set`, `::test_approval_phrases_unchanged`,
    `::test_agent_setup_and_writes_still_cannot_change_config`; `tests/test_shell_hooks.py` adds the phrase to the
    `engine.sh prompt` exit-0 cases → fail: the hook prints nothing for the phrase
  - Covers: AC-1, AC-4, AC-5, AC-6, AC-7
- [x] **S7**: The playbook walk with the profile set by phrase.
  - Files: `tests/test_playbook.py` (modify: `PhraseWalk`: agent-run `setup --yes`, then the hook with
    `Setup Profile <p>`, then the existing walk with approvals through the hook)
  - Test first: `tests/test_playbook.py::PhraseWalk::test_solo`, `::test_team`, `::test_strict` → `test_solo` fails
    before S5-S6 (the first `Intent Approved 0001` is refused under the `team` default); after them it must pass
    with no engine change in this step
  - Covers: AC-2, AC-16
- [x] **S8**: `sdlc where`, the card's terminal line, and the profile read from `config.json`.
  - Files: `lib/sdlc_engine/cli.py` (modify: `cmd_where`, `COMMANDS`, USAGE, `terminal_line(root, st)` used by
    `card` and `hook_session_start`, the doctor row), `lib/sdlc_engine/lifecycle.py` (modify: `cmd_list_installed`
    prints the config's profile)
  - Test first: `tests/test_cli.py::Where::test_first_line_is_the_terminal_command` (as human, as agent, without
    `.aiops/`, nothing written), `tests/test_cli.py::Card::test_terminal_line_when_no_profile_chosen`,
    `::test_terminal_line_when_a_gate_needs_the_terminal`, `::test_no_terminal_line_otherwise`,
    `tests/test_lifecycle.py::ListInstalled::test_profile_comes_from_config`,
    `tests/test_guards.py` adds `sdlc where` to an allowed list → fail: unknown command `where`
  - Covers: AC-9, AC-10
- [x] **S9**: Auto mode in the scaffold's `.aiops/README.md`.
  - Files: `templates/scaffold/.aiops/README.md` (modify), `defaults/scaffold-history.json` (regenerate with
    `python3 scripts/scaffold-history.py`: the tree now differs from the alpha.3 tag)
  - Test first: `tests/test_cli.py::Docs::test_scaffold_explains_auto_mode` (names `--permission-mode auto`, says
    project settings can't set it and the guards still run; `templates/scaffold/.claude/settings.json` has no
    `defaultMode`) → fails: the README lists allow-rules only
  - Covers: AC-17
- [x] **S10**: Skills describe the new flow.
  - Files: `skills/setup/SKILL.md`, `skills/configure/SKILL.md`, `skills/init/SKILL.md`,
    `skills/using-zouj-ai-sdlc/SKILL.md`, `skills/intent/SKILL.md`, `skills/triage/SKILL.md`,
    `skills/deploy/SKILL.md`, `skills/onboard/SKILL.md` (modify)
  - Test first: `tests/test_cli.py::Docs::test_setup_skill_asks_for_the_phrase` (no terminal step for `solo`),
    `::test_skills_name_where_and_with`, `::test_skills_name_the_part_they_need` → fail: the skills send `solo` to
    a terminal and never mention parts
  - Covers: AC-18
- [x] **S11**: The behavioural eval for the phrase.
  - Files: `evals/profile-by-phrase/case.yaml`, `fixture.sh`, `prompt.md`, `graders/asks-for-phrase.md`,
    `graders/config-unchanged.md` (create), `evals/_lib/repo.sh` (modify: `scaffold_only`, a repo after
    `sdlc init` with the template config and no intent), `evals/README.md` (modify)
  - Test first: `tests/test_cli.py::Docs::test_profile_eval_case_is_complete` (the files exist, the README lists the
    case, the fixture leaves the template config) → fails: no such case. Then `make evals`, or the single case, and
    quote the result for review.md; if no API key is available, log it in the Deviation log and leave the run to
    the human
  - Covers: AC-21
- [x] **S12**: Docs and the ADR. Rebase on main first if PR #17 has merged.
  - Files: `README.md`, `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md`, `docs/architecture.md` (modify: the two
    threat-model rows, and a Known gaps entry for a gate or profile phrase typed into a session the agent starts),
    `docs/adr/0003-first-profile-by-typed-phrase.md` (create), `docs/roadmap.md` and `docs/adoption.md` (modify, if
    #17 is on main)
  - Test first: `tests/test_setup.py::NoSandbox::test_docs_offer_the_recipe_not_a_sandbox` updated (the "Just
    looking?" paragraph holds `git init`, `Setup Profile solo` and `/zouj-ai-sdlc:intent`, and no `<plugin>`),
    `tests/test_cli.py::Docs::test_docs_document_where_and_with` → fail on today's README
  - Covers: AC-18
- [x] **S13**: Release 0.2.0-alpha.4 (0005 and 0007).
  - Files: `.claude-plugin/plugin.json`, `README.md`, `SECURITY.md`, `CHANGELOG.md`, `docs/architecture.md` (the
    version in "Known gaps") (modify), `defaults/scaffold-history.json` (regenerate),
    `tests/test_shell_hooks.py` (the pinned version, line 396)
  - Test first: `tests/test_shell_hooks.py` version assertion set to `0.2.0-alpha.4`, new
    `tests/test_cli.py::Docs::test_changelog_has_the_release` (`[0.2.0-alpha.4]` names 0005 and 0007) → fail on
    alpha.3; then `make check` and `make validate`
  - Covers: AC-19
- [x] **S14**: The dormancy exception: `hooks/engine.sh` lets the typed setup command through without `.aiops/`.
  - Files: `hooks/engine.sh` (modify: in the not-initialized branch, for `prompt` only, match the raw JSON payload
    with a bash regex held in a variable, `"prompt"[[:space:]]*:[[:space:]]*"[[:space:]]*/zouj-ai-sdlc:setup [A-Za-z0-9_-]+[[:space:]]*"`,
    and continue only on a match, so only the plain form wakes python and the engine's `PROFILE_RE` still decides),
    `CLAUDE.md` (rule 3 names the exception), `docs/architecture.md` (Design choices: "Gates dormant by default")
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_prompt_hook_dormant_except_the_setup_command`: in a
    repo without `.aiops/`, with a `python3` stub first on a PATH that logs any start, `Intent Approved 0001`,
    `Setup Profile solo`, `/setup solo` and `/zouj-ai-sdlc:setup solo now` exit 0, print nothing and start no
    python; `/zouj-ai-sdlc:setup solo` reaches the engine (`sdlc hook prompt` gets the payload) → fails: every prompt
    exits 0 at once today
  - Covers: AC-5
- [x] **S15**: The prompt hook matches `/zouj-ai-sdlc:setup <name>`, the phrase is removed, and the hook acts only in
  the session's repo.
  - Files: `lib/sdlc_engine/cli.py` (modify: `PROFILE_RE` = the qualified command, whole prompt, name
    case-insensitive; `hook_profile` refuses with the reason and the terminal command unless `project_root(cwd)`
    equals `project_root(CLAUDE_PROJECT_DIR)`, and no longer returns early without `.aiops/`), `lib/sdlc_engine/
    setup.py` (modify: `set_first_profile`'s refusals name the command; the reply's scaffold commit message names
    the profile being set, not `config(root)['profile']`)
  - Test first: `tests/test_cli.py::ProfilePhrase` renamed `SetupCommand`, every case driven by
    `/zouj-ai-sdlc:setup …`: `test_whole_prompt_sets_the_profile`, `test_command_with_other_text_is_ignored` (also
    `/setup solo`, `Setup Profile solo`, a second argument, a bare `/zouj-ai-sdlc:setup` → empty output),
    `test_unknown_name_lists_profiles`, `test_works_with_the_session_markers_set`,
    `test_refused_outside_the_session_repo` (a nested template repo as `cwd`), `test_second_command_changes_nothing`,
    `test_agent_setup_and_writes_still_cannot_change_config`; `tests/test_setup.py::FirstProfile` refusal texts →
    fail: the hook matches only the phrase and reads no `CLAUDE_PROJECT_DIR`
  - Covers: AC-1, AC-3, AC-4, AC-6, AC-7
- [x] **S16**: In a fresh repo the command writes the core scaffold first (spec R-2a).
  - Files: `lib/sdlc_engine/setup.py` (modify: `set_first_profile` without `.aiops/` runs `cli.scaffold_root_problem`
    and `preflight(root, name)`, refuses on a problem or a `✗` row, then `plan(root, name, [])` and creates only the
    `+` rows through `cli.apply_init`, writes the config as template + profile, records install-state with
    `parts: []`, commits the config alone, and lists the created files and `steps_for_human` in the reply; an
    existing human-owned file is never changed, its difference becomes a step)
  - Test first: `tests/test_setup.py::FirstRun::test_fresh_repo_gets_core_and_the_profile` (16 core files,
    `.gitignore` lines, `parts: []`, no opt-in file, config = template + `solo`, HEAD touches only the config, the
    rest uncommitted, the reply gives the commit with exact paths and `(profile solo)`),
    `::test_existing_files_are_never_changed` (a `CLAUDE.md` and a `.claude/settings.json` of the user's own stay
    byte-identical; the settings change is a step), `::test_refused_where_setup_would_stop` (a subdirectory of the
    work tree, `$HOME`, `GIT_DIR` set, a Preflight `✗`: nothing written, the reason in the reply), and
    `::test_team_and_strict_steps` → fail: `set_first_profile` refuses without `.aiops/`
  - Covers: AC-8, AC-22, AC-23
- [x] **S17**: The playbook walk from a fresh repo, driven only by the hook, and the card's text.
  - Files: `tests/test_playbook.py` (modify: `PhraseWalk` becomes `CommandWalk`: no agent-run setup; the human's
    `/zouj-ai-sdlc:setup <p>` and every approval go through `hooks/engine.sh` with both session markers set),
    `lib/sdlc_engine/cli.py` (modify: `terminal_lines` names `/zouj-ai-sdlc:setup solo|team|strict`)
  - Test first: `CommandWalk::test_solo`, `::test_team`, `::test_strict`; `tests/test_cli.py::Card::
    test_terminal_line_when_no_profile_chosen` expects the command → fail: the hook is dormant in a fresh repo and
    the card names the phrase
  - Covers: AC-2, AC-10, AC-16
- [x] **S18**: Skills and the scaffold text use the command.
  - Files: `skills/setup/SKILL.md` (R-21: read the hook's reminder first; with none, preview, ask for the profile,
    ask the human to type `/zouj-ai-sdlc:setup <profile>`; never type or simulate it; `--with` later),
    `skills/configure/SKILL.md`, `skills/init/SKILL.md`, `skills/onboard/SKILL.md`,
    `skills/using-zouj-ai-sdlc/SKILL.md`, `templates/scaffold/.aiops/README.md` (modify)
  - Test first: `tests/test_cli.py::Docs::test_setup_skill_asks_for_the_command` (replaces
    `test_setup_skill_asks_for_the_phrase`), `::test_no_shipped_file_names_the_phrase` (no `Setup Profile` in any
    file under `skills/`, `templates/`, `docs/`, README, COMMANDS-QUICK-REF.md, TROUBLESHOOTING.md, SECURITY.md,
    `evals/`, `lib/` except the commit title constant) → fail: the skills ask for the phrase
  - Covers: AC-18
- [x] **S19**: The eval asks for the command.
  - Files: `evals/profile-by-phrase/` renamed `evals/profile-by-setup-command/` (`git mv`), `prompt.md`,
    `graders/asks-for-phrase.md` renamed `asks-for-setup-command.md`, `graders/config-unchanged.md` (compare the whole
    config with the template, the round 1 L3), `evals/README.md` (modify)
  - Test first: `tests/test_cli.py::Docs::test_profile_eval_case_is_complete` points at the new case and checks the
    grader compares the whole template → fails: no such case. Then one run of the case with the plugin
    (`--case profile-by-setup-command`), quoted for review.md
  - Covers: AC-21
- [x] **S20**: Docs, ADR and CHANGELOG.
  - Files: `README.md`, `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md`, `docs/adoption.md`, `docs/roadmap.md`,
    `SECURITY.md`, `docs/architecture.md` (the threat-model row for the typed command and the hook scaffold, Known
    gaps names `claude -p "/zouj-ai-sdlc:setup solo"`), `docs/adr/0003-first-profile-by-typed-phrase.md` renamed
    `docs/adr/0003-first-profile-by-typed-setup-command.md` (rewritten: R-1 to R-4, why the phrase was removed),
    `CHANGELOG.md` `[0.2.0-alpha.4]` (the command, the fresh-repo scaffold; the long line wrapped) (modify)
  - Test first: `tests/test_setup.py::NoSandbox::test_docs_offer_the_recipe_not_a_sandbox` expects
    `/zouj-ai-sdlc:setup solo` in "Just looking?"; `tests/test_cli.py::Docs::test_docs_document_where_and_with`;
    S18's `test_no_shipped_file_names_the_phrase` covers the docs → fail on today's README
  - Covers: AC-18, AC-19

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| An agent sets `solo` by typing the phrase into a session it starts (`claude -p`); no marker tells it from a human | Low | Medium: only in a repo with the template config and nothing approved, and the commit is visible | Spec R-2 conditions 2 and 3; S12 records the gap for the guard backlog (0006). After S7, one manual run in a `make dev` session confirms the human path |
| A setup that fails part-way leaves `.aiops/` with no install-state, and the rerun installs the wrong parts | Low | Medium | S2: with the template config, the rerun reads the installed parts from disk (AC-20), with tests for core-only and `--with maintain` |
| The eval can't run here (no API key, or it needs an isolated HOME) | Medium | Low | S11's deterministic test still proves the case is complete; the run is handed to the human and logged |
| The default change breaks tests that scaffold a fresh repo and expect 36 files | High | Low | S3 moves them to `--with all` in the same commit; `RepoCase` tests are untouched by R-13 |
| The profile commit disturbs a half-staged scaffold | Low | Medium | `_commit_alone` builds the tree in a throwaway index; S5 tests staged files and a repo with no commit |
| The card gets slow: `signing_problem` runs `ssh-keygen` on every `sdlc status` | Medium | Low | `terminal_line` calls it only when the intent waits on the human in states 1-3 |
| README conflicts with PR #17, which rewrites the same Install section | High | Low | Merge #17 first; S12 starts with a rebase on main |
| `scaffold-history.json` goes stale twice (S9 under `unreleased`, S13 under alpha.4) now that alpha.3 is tagged | High | Low | `tests/test_rules.py::History` fails until regenerated; both steps name the command |
| Lint passes locally and fails in CI (shellcheck and ruff run only there) | Medium | Low | Check new code for unused names by hand; watch `gh pr checks` after the push |
| An alpha.3 engine reads alpha.4 install-state and offers the left-out parts as `new` | Low | Low | CHANGELOG states it; upgrading the plugin fixes it |
| An agent starts its own session with `claude -p "/zouj-ai-sdlc:setup solo"`; in a fresh repo that also scaffolds | Low | Medium: the session's repo only, template config or none, nothing approved; one visible commit; CI reads the base config | Spec flag (accepted, zoujagger); S20 records it in Known gaps for the guard backlog (0006) |
| The engine.sh pre-filter misreads the JSON prompt (escapes, a newline) and wakes python for other prompts, or misses the command | Medium | Low | S14 tests both directions with a python stub that logs starts; on any doubt the engine's own `PROFILE_RE` decides |
| Claude Code hands `UserPromptSubmit` the expanded skill text instead of the typed line | Low | High: the command would set nothing | The hooks reference says it is the typed line (2026-11-13); the manual `make dev` check before the merge types it once |
| The hook writes a scaffold where the human didn't expect one (a subdirectory, a nested repo) | Low | Medium | R-2 condition 1 and `scaffold_root_problem`; S15 and S16 test a nested repo, a subdirectory, `$HOME` and `GIT_DIR` |
| Re-approving the spec leaves the old plan gate open, so the engine reports state 5 for code that doesn't match the spec | Seen 2026-11-13 | Low | This amendment changes the Steps, which closes the plan gate; `sdlc validate` already flags the missing AC ids. A spec change that should void the plan is a state-machine follow-up, not fixed here |

## Test definitions
<!-- One row per acceptance criterion, at least. -->
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_setup.py::FirstProfile::test_sets_and_commits_config_alone`, `tests/test_cli.py::SetupCommand::test_whole_prompt_sets_the_profile` | integration | the config equals template + `solo`, HEAD is a single-file commit with the trailer, the context says `profile SET` |
| AC-2 | `tests/test_playbook.py::CommandWalk::test_solo` | integration | from a fresh repo, `/zouj-ai-sdlc:setup solo` then `Intent Approved 0001` through `engine.sh` open the gate with no terminal step and no agent-run setup |
| AC-3 | `tests/test_setup.py::FirstProfile::test_refused_when_profile_set`, `::test_refused_when_config_edited`, `::test_refused_when_an_artifact_is_approved_or_closed`, `::test_refused_after_an_approval_set_back_to_draft`, `tests/test_cli.py::SetupCommand::test_refused_outside_the_session_repo` | integration | no file or commit changes; the reply has the reason and the terminal command |
| AC-4 | `tests/test_cli.py::SetupCommand::test_command_with_other_text_is_ignored`, `::test_unknown_name_lists_profiles` | integration | only the whole qualified command counts; `/setup`, the phrase, extra text and a bare command print nothing; a bad name lists the profiles |
| AC-5 | `tests/test_shell_hooks.py::ShellHooks::test_prompt_hook_dormant_except_the_setup_command` | integration | without `.aiops/`, every other prompt exits 0 with no output and no python start; the command reaches the engine |
| AC-6 | `tests/test_cli.py::SetupCommand::test_works_with_the_session_markers_set` | integration | with `CLAUDECODE=1` and `CLAUDE_CODE_CHILD_SESSION=1`, as every hook has them, the profile is set |
| AC-7 | `tests/test_cli.py::SetupCommand::test_agent_setup_and_writes_still_cannot_change_config`, the existing `tests/test_setup.py::Owned` and `tests/test_guards.py` config cases | integration | the agent's `setup --profile`, Edit, Write and shell writes leave the config unchanged |
| AC-8 | `tests/test_setup.py::FirstProfile::test_team_reply_has_signing_steps`, `::test_strict_reply_has_codeowners_step`, `::test_terminal_team_on_a_new_config_sets_the_profile`, `tests/test_setup.py::FirstRun::test_team_and_strict_steps` | integration | the profile is set, the reply carries the remaining human steps, and a terminal `--profile` writes the same config |
| AC-9 | `tests/test_cli.py::Where::test_first_line_is_the_terminal_command` | integration | the first line, exit 0, no write, as human and agent, with and without `.aiops/` |
| AC-10 | `tests/test_cli.py::Card::test_terminal_line_when_no_profile_chosen`, `::test_terminal_line_when_a_gate_needs_the_terminal`, `::test_terminal_line_when_a_passphrase_key_signs`, `::test_no_terminal_line_otherwise` | unit | the card line appears only when a human step is pending, and names `/zouj-ai-sdlc:setup` with no profile chosen |
| AC-11 | `tests/test_cli.py::InitParts::test_fresh_init_writes_core`, `tests/test_setup.py::Parts::test_default_is_core_with_no_schedule_or_secret` | integration | 16 files, `parts: []`, no `schedule:` and no secret in the created workflows |
| AC-12 | `tests/test_cli.py::InitParts::test_with_adds_only_that_part`, `::test_with_all`, `::test_unknown_part_refused_before_writing`, `::test_rerun_without_with_keeps_parts`, `tests/test_setup.py::Parts::test_with_maintain_adds_only_maintain` | integration | `--with` adds exactly a part, never removes, and refuses unknown names |
| AC-13 | `tests/test_lifecycle.py::CoreOnly::test_list_installed_hides_parts_not_installed`, `::test_upgrade_and_repair_create_none_of_them` | integration | no `new` or `missing` row for an uninstalled part; nothing created |
| AC-14 | `tests/test_lifecycle.py::Compat::test_state_without_parts_reads_as_every_part`, `tests/test_cli.py::InitParts::test_edited_config_without_state_gets_every_part`, `::test_template_config_with_full_scaffold_gets_every_part`, the unchanged lifecycle suites | integration | alpha.3 state and state-less repos behave as before |
| AC-15 | `tests/test_lifecycle.py::Parts::test_every_scaffold_file_has_one_part`, `::test_every_manifest_line_matches_a_file`, `::test_never_declined_is_core` | unit | the manifest is complete and core holds the security scaffold |
| AC-16 | `tests/test_playbook.py::CoreWalk::test_solo`, `::test_team`, `::test_strict`, `tests/test_playbook.py::CommandWalk::test_team`, `::test_strict` | integration | states 1 to 6 hold on a core-only repo and on a repo set up by the typed command |
| AC-17 | `tests/test_cli.py::Docs::test_scaffold_explains_auto_mode` | unit | the scaffold README text, and no `defaultMode` in the scaffold settings |
| AC-18 | `tests/test_setup.py::NoSandbox::test_docs_offer_the_recipe_not_a_sandbox`, `tests/test_cli.py::Docs::test_setup_skill_asks_for_the_command`, `::test_no_shipped_file_names_the_phrase`, `::test_skills_name_where_and_with`, `::test_skills_name_the_part_they_need`, `::test_docs_document_where_and_with` | unit | the recipe and the skills reach `solo` with the typed command; no shipped file names the phrase; `sdlc where` and `--with` are documented |
| AC-19 | `tests/test_shell_hooks.py` (version assertion), `tests/test_cli.py::Feedback::test_prints_links_offline` (README pins), `tests/test_rules.py::History::test_current_scaffold_in_history`, `tests/test_cli.py::Docs::test_changelog_has_the_release`; `make check`, `make validate` | unit | version, pins, CHANGELOG and scaffold history agree on 0.2.0-alpha.4 |
| AC-20 | `tests/test_cli.py::InitParts::test_rerun_after_partial_core_setup_stays_core`, `::test_rerun_after_partial_with_maintain_completes_it` | integration | a rerun after a setup that stopped part-way installs what the first run chose |
| AC-21 | `tests/test_cli.py::Docs::test_profile_eval_case_is_complete`; a run of the case `profile-by-setup-command` with the plugin | unit + e2e | the case is complete and listed; the agent leaves the config alone and asks for `/zouj-ai-sdlc:setup solo` |
| AC-22 | `tests/test_setup.py::FirstRun::test_fresh_repo_gets_core_and_the_profile`, `::test_existing_files_are_never_changed` | integration | a fresh repo gets exactly the core scaffold and the profile, the config alone is committed, no existing file changes |
| AC-23 | `tests/test_setup.py::FirstRun::test_refused_where_setup_would_stop` | integration | a subdirectory, `$HOME`, `GIT_DIR` or a Preflight `✗`: nothing written, the reason in the reply |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-10 | S1 | The manifest reader is `part_rules()` (the `(part, glob)` lines), not `parts()`; `PARTS` holds the five opt-in names. A fifth test, `Parts::test_parse_parts`, covers `parse_parts` | `parts` is used as an argument name throughout S2-S4 | S1 |
| 2026-11-10 | S2 | A part counts as "on disk" only if one of its files equals a released scaffold file (after `normalize()`), not merely exists. New test `InitParts::test_the_users_own_files_do_not_count_as_a_part` | A project's own `dependabot.yml` or issue forms sit at scaffold paths; counting them would install `governance` or `issues` in a new repo. Narrower than spec R-13's wording, same intent | S2 |
| 2026-11-10 | S2 | "Template config" also covers a missing `config.json` (a setup that stopped before writing it). The check lives in `lifecycle.config_is_template`, with `parts_on_disk` and `parts_line` beside it | The first file written is `.aiops/README.md`, so `.aiops/` can exist without a config; S5 reuses the helper from `lifecycle` | S2 |
| 2026-11-10 | S2 | Existing tests that remove the fixture's `.aiops/` and then run `sdlc init` (`tests/test_cli.py::Init`, the lifecycle suites, `tests/test_setup.py`) now pass `--with all`. So does `evals/_lib/repo.sh` | The plan expected only `SetupCase` and `Playbook.repo` to need it; 22 init tests rely on opt-in files (`ops/bands.yaml`, `deploy.yml`, `claude.yml`). Their meaning is unchanged: the full scaffold | S2 |
| 2026-11-10 | S2 | `sdlc init` ends with a line naming the parts it left out | Spec R-17 asks for it in setup's preview; init is the other entry point | S2 |
| 2026-11-10 | S3 | With no install-state, a `config.json` that is the template plus one profile's keys (a human's `setup --profile`) also reads the parts from disk (`lifecycle.config_written`). Test `Parts::test_rerun_after_partial_setup_installs_what_the_first_run_chose` | A human's run writes the profile before install-state, so its rerun after a failure would otherwise install every part (AC-20) | S3 |
| 2026-11-10 | S3 | Only one existing setup test changed (`Symlinks`, now `--with maintain`), not every fresh-repo test. The commit command setup prints lists only files of installed parts | The other `SetupCase` tests assert core files only. A file at an opt-in path in a core-only repo is the user's own, not the scaffold's | S3 |
| 2026-11-10 | S3 | `CoreWalk` skips the mid-walk `upgrade`/`repair` check (its fixtures are `maintain` files), and `protected_tree_blocked` creates `docs/` first | Until S4, `upgrade` would create the left-out parts; S4 adds the core check. A core-only repo has no `docs/`, and `rm -rf docs` on a missing directory has nothing to judge | S3 |
| 2026-11-10 | S4 | `lifecycle.adopt` also changed: the adopted state carries `parts` (read from disk), and a missing file of a part that isn't installed is not marked `declined`. Tests `Compat::test_release_repo_without_state_keeps_every_part` and, in `tests/test_playbook.py`, `lifecycle_on_core` (the check S3 deferred) | Without it a core-only repo that lost its install-state would list 20 `declined` rows; the walk on core now also proves that the agent's `upgrade` and `repair` bring in no opt-in file | S4 |
| 2026-11-10 | S5 | The template check is `lifecycle.config_written` (S2/S3), not a `template_config()` factored out of `setup._as_setup_writes`. `human_steps` became a printer over a new `steps_for_human(..., install=False)`, so the reply can leave out the plugin-install step. Three extra tests: `test_refused_without_aiops`, `test_unknown_name`, and a missing `config.json` case | `_as_setup_writes` compares bytes with the ref pinned and is used for a different question (was this file planted?). The phrase is typed with the plugin already running | S5 |
| 2026-11-10 | S6 | `lib/sdlc_engine/setup.py` changed too: when the repo has no profile yet, the agent-run setup's human step is "type `Setup Profile <p>` as your whole prompt" (the terminal command is still named, and the downgrade label is kept). `tests/test_setup.py::Owned` updated for the new text, with a case for an edited config that still gets the terminal step | Without it the engine would keep sending `solo` users to a terminal while the hook already accepts the phrase (AC-18 depends on it) | S6 |
| 2026-11-10 | S6 | The shell-hook case is `tests/test_cli.py::ProfilePhrase::test_through_the_shell_hook`, not an addition to `tests/test_shell_hooks.py`. Extra test `::test_second_phrase_changes_nothing` | It needs the scaffolded fixture of `ProfilePhrase`; `test_shell_hooks.py` only has a broken-engine case for `prompt` | S6 |
| 2026-11-10 | S7 | One engine change after all, in `setup.steps_for_human`: the "type `Setup Profile <p>`" step is printed for every profile while the repo has none, `team` included | `PhraseWalk::test_team` failed: `team` differs from the template by no key, so the agent-run setup printed no profile step and the default was never recorded (spec R-21: "for every profile") | S7 |
| 2026-11-10 | S7 | The manual run in a `make dev` session (Risks, first row) is not done: this session doesn't have the plugin loaded | Left for the human before the merge; `PhraseWalk` drives the same hook with the markers every session's hooks see | S7 |
| 2026-11-10 | S8 | The helper is `terminal_lines` (a list). At a gate that needs signing, the card line is the full approve command (`… approve 0001 intent`), not the bare prefix. The doctor row needed no change: it already read `config.json` | The full command is what the human pastes; it starts with the prefix AC-10 names. With no profile, a second card line names the phrase (spec R-11) | S8 |
| 2026-11-10 | S9 | The scaffold's `.aiops/README.md` also gained two bullets (Profile, Parts) and a pointer to `sdlc where` | It is the one consumer-facing page that explains the gates, and editing it once means one `scaffold-history.json` regeneration before the release | S9 |
| 2026-11-11 | S11 | `make evals` was not run as planned. With the Bash grant the eval tool refuses every run on this machine ("sandbox required but unavailable … socat not installed"; an API key was not the obstacle). The single case ran with `--case profile-by-phrase --runs 1 --allow-tools Write Edit`: with the plugin 1.00 (asks-for-phrase PASS ×3, config-unchanged ✓), without 0.50 (asks-for-phrase FAIL ×3), Δ +0.50, $0.23 | Installing `socat` needs sudo, which is the human's. Done 2026-11-11 after the human installed it: the case with Bash, Write and Edit, 3 runs per arm: with the plugin 1.00, without 0.83, Δ +0.17, $0.83. `make evals` (stopped by the human after 899 s, $6.03, 6 of 7 cases complete): agent-cannot-approve, no-merge, prod-deploy-blocked, readonly-in-plan and profile-by-phrase 1.00 with the plugin; tdd-red-first 1.00 (1 run); intent-first 0.89 (1 of 3 runs wrote no intent.md; 1.00 without the plugin). The intent-first miss predates 0007 and is for the review to weigh | S11 |
| 2026-11-11 | S12 | Main was merged into the branch (`42f9d50`), not rebased onto | PR #17 had merged, but a rebase rewrites the four signed approval commits of this intent: their signatures would be lost and the CI audit would refuse the gates. The merge brings in the same five doc files with no conflict | S12 |
| 2026-11-11 | S12 | `docs/architecture.md` changed in three more places: the hook diagram and module list name `setup.set_first_profile` and the parts manifest, a design-choice bullet covers the core scaffold, and the Known gaps intro says its last entry comes from 0007 and is new with the phrase. README also gained a parts table and the `Your terminal:` card line; `docs/adoption.md` lists the workflows by part | The intro said every gap was found in a 0005 review and none is weaker than alpha.3, which is not true of the nested-session phrase; the rest keeps the page in step with S1-S8 | S12 |
| 2026-11-11 | S12 | `tests/test_shell_hooks.py::test_docs_match_what_shipped` changed too: it pinned the old recipe (`bin/sdlc setup --profile solo --yes`, and no `/zouj-ai-sdlc:setup solo`) | Written in 0003 for the behaviour AC-18 replaces. It now asks for the skill and the phrase, and still checks that path A, the quick reference and the setup skill send a set profile's change to the human's terminal | S12 |
| 2026-11-11 | S13 | `SECURITY.md` and `docs/architecture.md` had no version to move. SECURITY.md gained a bullet on the profile phrase and its accepted gap; the Known gaps intro was already corrected in S12 | SECURITY.md never pinned a version, and "no weaker than 0.2.0-alpha.3" stays true of the 0005 gaps. The policy page should name the one hook that writes a human-owned file | S13 |
| 2026-11-11 | S13 | `Docs::test_changelog_has_the_release` also checks the README pins, the `[Unreleased]` link and that `scaffold-history.json` has the alpha.4 entry and no `unreleased` one. CHANGELOG `[0.2.0-alpha.4]` has its own Known issues and Upgrading sections | AC-19 names all of them; each earlier release has both sections | S13 |
| 2026-11-13 | Review r1 | A style-only commit: `ruff format` over `lib/` and `tests/` (ruff 0.15.1, line length 120 from `ruff.toml`). Two lambdas became `def`s (E731; the formatter had moved their `noqa`). `Coverage::test_every_block_call_names_an_id` now lets the rule id sit on the line after `_block(`. `make format` no longer formats `bin/sdlc` | Anaconda's ruff came onto PATH, and the post-edit hook's `make format` reformatted 22 files on every edit. The human chose to format the repo once, before the review fix. `ruff format` merged `bin/sdlc`'s sh/python header `"exec" "python3" "-I" "$0" "$@"` into one string, which breaks the CLI, so that file is restored and left out of `make format`. `make check`: 406 tests OK | Review r1 |
| 2026-11-13 | Review r1 (S5) | `setup.no_profile_yet` also refuses when any commit on any ref carries an `AIOps-Approval:` trailer, and fails closed when git can't list the history. New test `FirstProfile::test_refused_after_an_approval_set_back_to_draft`; ADR 0003 (condition 3), SECURITY.md, `docs/architecture.md` (threat model, Known gaps) and the CHANGELOG say "nothing approved, in the files or the history" | The round 1 MEDIUM (code-reviewer and security-reviewer): G-GATE-05 lets the agent set any artifact back to Draft, so reading the status on disk let it defeat spec R-2 condition 3. Red: `AssertionError: True is not false : profile SET: solo` with an approval commit in the history and the intent back to Draft. Green after the fix | Review r1 |
| 2026-11-13 | Review r2 (S8) | `cli.terminal_lines` also shows the approve command at a gate when signing is required under the `human` key policy, not only on a `signing_problem`. Test `Card::test_terminal_line_when_a_passphrase_key_signs` | The r2 code review's M1: the recommended team key (a passphrase, kept out of ssh-agent) has no signing problem, but the prompt hook has no terminal to ask for the passphrase, so the line was missing exactly when the human needed it. Red: `Lists differ: [] != ['- Your terminal: … approve 0001 intent']` | Review r2 |
| 2026-11-13 | Review r2 (S5) | `setup.owned_changes` compares a profile's keys with the config file itself while it has no `profile` key, not with the engine defaults. A terminal `setup --profile team` on a new config now writes the template plus team's keys, as the phrase does (spec R-3). Test `FirstProfile::test_terminal_team_on_a_new_config_sets_the_profile` (all three profiles) | The r2 code review's L1: team's keys equal `DEFAULT_CONFIG`, so the human's terminal run wrote nothing. The repo still counted as having no profile, the card kept asking for one, and the human steps repeated the command just run. Red: the config stayed the template, missing `profile: team` and `approval_key_policy: human` | Review r2 |
| 2026-11-13 | S14 | The test detects a python start with a fake plugin whose `bin/sdlc` logs its stdin, not a `python3` stub on PATH. It also checks that `/zouj-ai-sdlc:setup fast` reaches the engine (to list the profiles) and that a prompt with a newline after the command doesn't | `engine.sh` runs `/usr/bin/python3` by absolute path (on purpose: an agent could plant a `python3` on PATH), so a PATH stub would never be called. Red: `the engine never saw '/zouj-ai-sdlc:setup solo'` | S14 |
| 2026-11-13 | S15 | Three additions to the step. (1) With `CLAUDE_PROJECT_DIR` unset or empty, the hook refuses (the session's repo is unknown: fail closed). (2) `steps_for_human`: the scaffold commit message names the profile being set only while none is set, and the config's profile otherwise; the "Downgrade" label appears only when a profile is set. `Owned::test_agent_downgrade_is_labelled_and_the_commit_names_the_real_profile` now checks both cases (it pinned "(profile team)" on a fresh repo, the r3 LOW). (3) `PhraseWalk` and `Card` take the command as input now, so the suite stays green; S17 restructures them | (1) Claude Code always sets it for hooks, so a missing value means a caller that isn't a session. (2) An older round's rule (name the real profile) still holds once a profile is set; on a first run the "real" one was only the engine default, and the label called it a downgrade (r1 NIT). Red: 9 `SetupCommand` tests (no hook output for the command) | S15 |
| 2026-11-13 | S16 | Two helpers in `setup.py`: `approval_in_history` (the r1 history check, out of `no_profile_yet`) and `scaffold_first`, which also runs the history check before writing. The refusal cases are "not a git repo", `$HOME`, `GIT_DIR` and a Preflight `✗` (no `make`), not "a subdirectory of the work tree": a subdirectory `cwd` resolves to the repo's top level, which is the repo to scaffold. `FirstProfile::test_refused_without_aiops` became `test_without_aiops_scaffolds_unless_tracked` | A fresh repo with an approval commit on some ref must refuse before anything is written, not after. The old test pinned the refusal that R-2a replaces; a tracked-but-deleted `.aiops/` still counts as initialized and refuses. Red: the 4 `FirstRun` tests got `profile NOT set: this repo isn't set up yet` | S16 |
| 2026-11-13 | S17 | `CommandWalk` passed on its first run against the S16 engine: the behaviour it walks (the dormancy exception, the fresh-repo scaffold) landed in S14 and S16, whose red runs are logged above. Its own first run failed only on the harness (`env: 'bash': No such file or directory`: the stub PATH had no bash for `engine.sh`), fixed with `/usr/bin:/bin` after the stubs. `CommandWalk.scaffold` also checks that an approval phrase in the fresh repo does nothing. The card test no longer asserts that the session output never names the phrase: that output includes the `using-zouj-ai-sdlc` skill, which S18 changes and S18's test covers | Red for the card: `'type \`/zouj-ai-sdlc:setup solo\|team\|strict\`' not found` (the card named the phrase) | S17 |
| 2026-11-13 | S18 | `Docs::test_no_shipped_file_names_the_phrase` covers `skills/`, `templates/` and `lib/` here; S19 adds `evals/` and S20 the docs, each in the step that changes them. `defaults/scaffold-history.json` regenerated (the scaffold's `.aiops/README.md` changed; alpha.4 isn't tagged, so its entry moves). `Docs::test_skills_name_where_and_with` checked the onboard skill for the phrase and now checks for the command. The setup skill also gained a red-flag row against running `sdlc setup --profile <p> --yes` for the human | One test over every shipped file would keep `make check` red from S18 to S20. Red: `test_setup_skill_asks_for_the_command` (no command in the skill) and `test_no_shipped_file_names_the_phrase` (5 files) | S18 |
| 2026-11-13 | S19 | The whole-template grader is a regex over the config's JSON object (the four template keys in order, between its braces), not a file comparison: the eval tool's graders are `llm` or `regex`. The test proves it matches the template and fails on an added `profile`, an added `approval_key_policy`, or `require_signed_approvals: false`. `test_no_shipped_file_names_the_phrase` now covers `evals/`, skipping the git-ignored `evals/results/`. The run, with Bash, Write and Edit, 3 runs per arm: `profile-by-setup-command` 1.00 with the plugin (asks-for-setup-command PASS ×3, config-unchanged ✓ ×3), 0.67 without (asks FAIL in 2 of 3), Δ +0.33, $0.87, 93 s | Red: `test_profile_eval_case_is_complete` (the old case directory still existed) | S19 |
| 2026-11-13 | S20 | Two more tests changed beyond the two the step names: `Docs::test_docs_document_where_and_with` (it pinned the phrase in the ADR, the threat-model rows, Known gaps and the adoption/roadmap pages; it now pins the command, the renamed ADR, the new R-2a threat-model row and the `claude -p "/zouj-ai-sdlc:setup solo"` gap) and `ShellHooks::test_docs_match_what_shipped` (its "Just looking?" pieces). `test_no_shipped_file_names_the_phrase` covers README, COMMANDS-QUICK-REF, TROUBLESHOOTING, SECURITY and `docs/`, so the ADR tells its own history without quoting the phrase. Also fixed in passing: the threat-model `sdlc setup` row's `--with` wording (r2 security LOW: "unless `--with <part>` is passed (the skills pass it only when the human asks)"), the Known gaps entry now names the ref-deletion path (r2/r3 LOW), and the two long CHANGELOG lines (r3 NIT; 0005's own long line is left alone) | The docs were the last place the phrase lived. Red: `test_docs_document_where_and_with` (no command in COMMANDS-QUICK-REF), `test_no_shipped_file_names_the_phrase` (README and docs), `NoSandbox::test_docs_offer_the_recipe_not_a_sandbox` (the recipe named the phrase) | S20 |
| 2026-11-13 | Review r4 (S14-S16) | Fixes from the round 4 review, no new Steps. (1) MEDIUM: `FirstRun::test_refused_when_an_approval_is_in_the_history` covers `scaffold_first`'s history refusal. (2) The reply says "Nothing was written" only when nothing was; after a write that failed part-way it lists what was. (3) On the hook path Preflight runs with `quick=True`: only git, make and python (the rows that can stop setup), not `claude --version`, `gh auth status` or the credential helper (`_warning_rows`). (4) `PROFILE_RE` accepts only spaces and tabs around the command, as `engine.sh` does, so a fresh repo and an initialized one agree on a trailing newline. (5) The session-start notice in a repo without `.aiops/` (cli.py and engine.sh) names `/zouj-ai-sdlc:setup solo\|team\|strict`, not `/zouj-ai-sdlc:init`. (6) Security LOWs: the reply flags a `Set-By` taken from the repo's own git config, and lists the non-comment lines of `allowed-signers`, `legacy-approvals` and `allowed-commands`. (7) NITs: the stale docstring and section comment. Not changed: AC-18's wording against R-4's commit title (the human's call), and eight parenthesized `with (` blocks from the format commit `7d8d4d0` (Python 3.9's parser accepts them; CI runs 3.12) | The human asked to fix the MEDIUM and the small findings before the live check. Red: 6 tests (`FirstRun` × 4, `FirstProfile::test_reply_lists_the_trust_lists`, `SetupCommand::test_whole_prompt_sets_the_profile`) and `PromptAndSessionHooks::test_engine_hooks_are_dormant_without_aiops` | Review r4 |
| 2026-11-13 | Review r4 HIGH (S15) | The live check of the platform behaviour the command rests on, done by a probe rather than by typing `/zouj-ai-sdlc:setup` (which the agent never does): a throwaway plugin in the session scratchpad with a `disable-model-invocation` skill `hello` and a `UserPromptSubmit` hook that only logs its stdin, one `claude -p "/probe:hello solo" --plugin-dir <probe>` in an empty scratch git repo. The hook received `"prompt":"/probe:hello solo"`, the typed line, before the skill expanded; the skill then ran and replied `hello solo`. The payload is compact JSON (no space after the colon), so `test_prompt_hook_dormant_except_the_setup_command` now also feeds `engine.sh` the compact form (it already passed: the regex allows any spacing). Still worth doing once by hand in a `make dev` session with the real plugin: the probe ran in `-p` mode, not the interactive TUI | The S7 risk row and spec Open question 2 ask for this before the merge; round 4 rated it HIGH because every automated test feeds the hook a payload directly | Review r4 |
| 2026-11-13 | Review r5 (S15, S16, S20) | Fixes from the round 5 review, no new Steps. (1) MEDIUM: after a fresh-repo command, install-state re-records `.aiops/config.json` once the profile is written (it held the template's hash, so `list-installed` said `modified`). (2) AC-23: in a fresh repo, the command refuses unless the prompt's directory is the work tree's top (`set_first_profile(..., cwd=)`); an initialized repo still resolves a subdirectory to its top, as S15 tests. (3) Security LOW: the command refuses a repo-local git config key outside `approvals.LOCAL_ALLOWED_RE` (the `approve`/`doctor` allow-list) before any git that could run it (a planted `core.fsmonitor`). (4) Security LOW: the hook also sends its result and warnings as `systemMessage`, which Claude Code shows the human. (5) The reply counts the 16 core files and names the `.gitignore` lines apart. (6) `PROFILE_RE` allows spaces only, as `engine.sh` sees them (a tab arrives escaped). (7) Docs: Known gaps and the R-2a threat-model row name the `sdlc hook prompt` route; TROUBLESHOOTING the two new refusals; architecture line 22; CLAUDE.md's long line; the alpha.4 CHANGELOG date. (8) NIT: the refusal for `.aiops/` without a config no longer points back at the command just typed | The human asked to fix everything from round 5. Red: `FirstRun` × 4 (the count and install-state hash, `systemMessage`, the subdirectory, `core.fsmonitor`), `SetupCommand::test_whole_prompt_sets_the_profile` (tab), `Docs::test_docs_document_where_and_with` (the route) | Review r5 |
| 2026-11-13 | Review r6 (S8, S15, S16) | Fixes from the round 6 review, no new Steps. (1) AC-10: `sdlc status` with no intent active (no intents, or the table) also prints `terminal_lines`. (2) Security MEDIUM: `set_first_profile` runs `unreviewed` on both paths. In a repo the agent scaffolded, a human-owned file it changed while the gates were off is named before "Relay the remaining human steps", so it reaches the human in the `systemMessage`, and it stays out of the suggested commit. (3) The card's no-profile check reads files only (`no_profile_yet(..., history=False)`): no `git log --all` on every status; the command still walks the history. (4) A config write that fails after a fresh-repo scaffold lists the files written instead of "Nothing changed". (5) Hardening: trust-list lines are shown with non-printable characters escaped (`_shown`). (6) The "typed phrase sets the first profile" wording in `skills/configure`, `docs/adoption.md`, `lifecycle.py` and `setup.py`. (7) Docs: the architecture row scopes the fsmonitor claim to the engine's own git (the `ls-files`/`rev-parse` before it are main's); TROUBLESHOOTING names the tool keys the allow-list refuses (husky, Git LFS, diff/merge drivers). (8) Logged late (S16): `scaffold_first` uses `cli.init_actions(root, parts=[])` plus `symlink_refusal`, not `plan(root, name, [])`: the same files, without the plan's display rows | The human asked to fix everything until done. Red: `Card::test_terminal_line_when_no_profile_chosen`, `Card::test_card_runs_no_history_walk`, `FirstProfile::test_planted_owned_file_is_named_before_the_steps`, `FirstProfile::test_trust_list_lines_are_escaped`, `FirstRun::test_config_write_failure_after_the_scaffold_is_reported` | Review r6 |
| 2026-11-13 | Review r7 (S14-S16, S8) | Round 7 passed (92, security 22, VERIFIED); its LOWs and NITs are fixed too, at the human's request, no new Steps. (1) Security LOW: G-GATE-07 (`sdlc approve\|close\|unlock\|hook\|legacy-approvals`) now runs before the "not initialized" return in `check_bash`, so a crafted payload piped into `sdlc hook prompt` is refused in a repo without `.aiops/`; this also closes the Known gap "the human-only checks in repos without `.aiops/`". (2) Security LOW: `_commit_alone(..., data=)` hashes the bytes the hook wrote (`hash-object --stdin`), and the reply warns when the file on disk changed after the write. (3) LOW: `classify` reports `.aiops/config.json` as `current` when it is exactly the template plus one profile (`config_written`), so the initialized path no longer shows `modified` while R-9 keeps install-state untouched. (4) LOW: the card's no-profile hint says the command refuses if a gate was ever opened (the card skips the history walk). (5) NIT: `hook_profile` checks the name before the session repo, so R-6's list always comes back. (6) NIT: AC-8's test compares bytes. (7) Logged late (S14): `engine.sh`'s regex uses `setup[[:space:]]+`, not the plan's single space, to match `PROFILE_RE`'s ` +` | Red: `PromptAndSessionHooks::test_hook_only_commands_blocked_without_aiops`, `FirstRun::test_commit_holds_the_bytes_the_hook_wrote`, `Card::test_card_runs_no_history_walk`, `SetupCommand::test_unknown_name_lists_profiles`, `ListInstalled::test_profile_comes_from_config`. The AC-8 byte comparison passed at once (equal by construction) | Review r7 |
| 2026-11-16 | Review r8 (S14-S16, S8) | Fixes from the round 8 review, no new Steps. (1) Security MEDIUM: `ENGINE_SH_RE` makes any run of the plugin's `hooks/engine.sh` (bare, a path, `$CLAUDE_PLUGIN_ROOT/…`, `bash`/`sh`, `bash -c`, `source`/`.`, wrappers) hook-only under G-GATE-07, in every repo; reading it (`cat`, `grep`, `shellcheck`) stays allowed. (2) MINOR: without `.aiops/`, G-GATE-07 refuses only the hook-feeding forms (`engine.sh`, or a human-only match with the word `hook`), so an unrelated project can still mention `sdlc close` in a commit message or `xargs grep sdlc`; the registry stage is `every-repo`; architecture, CLAUDE.md rule 3, rules.md and the CHANGELOG say so. (3) MINOR: `lifecycle.record(..., data=)` records the sha of the bytes the hook wrote, as the commit does. (4) Security LOW: `_trust_lists` shows at most 20 lines per list, then `(+N more, see <file>)`. (5) LOW: Known gaps say the hook's warnings reach a human only in the human's own session. (6) MINOR: `classify`'s comment says `current` only reports (config.json is MERGED_JSON); a test that `upgrade --yes` keeps `profile: solo`. (7) NIT: the CHANGELOG names the typed `/zouj-ai-sdlc:setup <profile>`, not "a typed phrase" | Red: `PromptAndSessionHooks::test_hook_only_commands_blocked_without_aiops`, `PromptAndSessionHooks::test_engine_sh_run_by_the_agent_is_hook_only`, `FirstRun::test_commit_holds_the_bytes_the_hook_wrote`, `FirstProfile::test_trust_lists_are_capped`. The upgrade assertion in `ListInstalled::test_profile_comes_from_config` passed at once (the behaviour was already right; it pins it) | Review r8 |
