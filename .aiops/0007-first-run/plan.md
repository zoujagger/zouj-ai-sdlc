---
id: 0007
title: First run in five minutes (profile by phrase, terminal command, core scaffold)
status: Approved
spec: ./spec.md
created: 2026-11-10
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-10T10:24:21Z
approved-via: cli
approved-sha256: 2aae560fecc6cfdfdcf91619f8e556272bed565a478c79d9bc5d73b8b39988aa
---

# Plan: First run in five minutes (profile by phrase, terminal command, core scaffold)

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
- [ ] **S12**: Docs and the ADR. Rebase on main first if PR #17 has merged.
  - Files: `README.md`, `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md`, `docs/architecture.md` (modify: the two
    threat-model rows, and a Known gaps entry for a gate or profile phrase typed into a session the agent starts),
    `docs/adr/0003-first-profile-by-typed-phrase.md` (create), `docs/roadmap.md` and `docs/adoption.md` (modify, if
    #17 is on main)
  - Test first: `tests/test_setup.py::NoSandbox::test_docs_offer_the_recipe_not_a_sandbox` updated (the "Just
    looking?" paragraph holds `git init`, `Setup Profile solo` and `/zouj-ai-sdlc:intent`, and no `<plugin>`),
    `tests/test_cli.py::Docs::test_docs_document_where_and_with` → fail on today's README
  - Covers: AC-18
- [ ] **S13**: Release 0.2.0-alpha.4 (0005 and 0007).
  - Files: `.claude-plugin/plugin.json`, `README.md`, `SECURITY.md`, `CHANGELOG.md`, `docs/architecture.md` (the
    version in "Known gaps") (modify), `defaults/scaffold-history.json` (regenerate),
    `tests/test_shell_hooks.py` (the pinned version, line 396)
  - Test first: `tests/test_shell_hooks.py` version assertion set to `0.2.0-alpha.4`, new
    `tests/test_cli.py::Docs::test_changelog_has_the_release` (`[0.2.0-alpha.4]` names 0005 and 0007) → fail on
    alpha.3; then `make check` and `make validate`
  - Covers: AC-19

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

## Test definitions
<!-- One row per acceptance criterion, at least. -->
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_setup.py::FirstProfile::test_sets_and_commits_config_alone`, `tests/test_cli.py::ProfilePhrase::test_whole_prompt_sets_the_profile` | integration | the config equals template + `solo`, HEAD is a single-file commit with the trailer, the context says `profile SET` |
| AC-2 | `tests/test_playbook.py::PhraseWalk::test_solo` | integration | agent-run setup, the phrase, then `Intent Approved 0001` opens the gate with no terminal step |
| AC-3 | `tests/test_setup.py::FirstProfile::test_refused_when_profile_set`, `::test_refused_when_config_edited`, `::test_refused_when_an_artifact_is_approved_or_closed` | integration | no file or commit changes; the reply has the reason and the terminal command |
| AC-4 | `tests/test_cli.py::ProfilePhrase::test_phrase_inside_other_text_is_ignored`, `::test_unknown_or_missing_name_lists_profiles` | integration | only the whole prompt counts; a bad name writes nothing and lists the profiles |
| AC-5 | `tests/test_cli.py::ProfilePhrase::test_dormant_without_aiops` | integration | exit 0, empty output, nothing written |
| AC-6 | `tests/test_cli.py::ProfilePhrase::test_works_with_the_session_markers_set` | integration | with `CLAUDECODE=1` and `CLAUDE_CODE_CHILD_SESSION=1`, as every hook has them, the profile is set |
| AC-7 | `tests/test_cli.py::ProfilePhrase::test_agent_setup_and_writes_still_cannot_change_config`, the existing `tests/test_setup.py::Owned` and `tests/test_guards.py` config cases | integration | the agent's `setup --profile`, Edit, Write and shell writes leave the config unchanged |
| AC-8 | `tests/test_setup.py::FirstProfile::test_team_reply_has_signing_steps`, `::test_strict_reply_has_codeowners_step` | integration | the profile is set and the reply carries the remaining human steps |
| AC-9 | `tests/test_cli.py::Where::test_first_line_is_the_terminal_command` | integration | the first line, exit 0, no write, as human and agent, with and without `.aiops/` |
| AC-10 | `tests/test_cli.py::Card::test_terminal_line_when_no_profile_chosen`, `::test_terminal_line_when_a_gate_needs_the_terminal`, `::test_no_terminal_line_otherwise` | unit | the card line appears only when a human step is pending |
| AC-11 | `tests/test_cli.py::InitParts::test_fresh_init_writes_core`, `tests/test_setup.py::Parts::test_default_is_core_with_no_schedule_or_secret` | integration | 16 files, `parts: []`, no `schedule:` and no secret in the created workflows |
| AC-12 | `tests/test_cli.py::InitParts::test_with_adds_only_that_part`, `::test_with_all`, `::test_unknown_part_refused_before_writing`, `::test_rerun_without_with_keeps_parts`, `tests/test_setup.py::Parts::test_with_maintain_adds_only_maintain` | integration | `--with` adds exactly a part, never removes, and refuses unknown names |
| AC-13 | `tests/test_lifecycle.py::CoreOnly::test_list_installed_hides_parts_not_installed`, `::test_upgrade_and_repair_create_none_of_them` | integration | no `new` or `missing` row for an uninstalled part; nothing created |
| AC-14 | `tests/test_lifecycle.py::Compat::test_state_without_parts_reads_as_every_part`, `tests/test_cli.py::InitParts::test_edited_config_without_state_gets_every_part`, `::test_template_config_with_full_scaffold_gets_every_part`, the unchanged lifecycle suites | integration | alpha.3 state and state-less repos behave as before |
| AC-15 | `tests/test_lifecycle.py::Parts::test_every_scaffold_file_has_one_part`, `::test_every_manifest_line_matches_a_file`, `::test_never_declined_is_core` | unit | the manifest is complete and core holds the security scaffold |
| AC-16 | `tests/test_playbook.py::CoreWalk::test_solo`, `::test_team`, `::test_strict`, `tests/test_playbook.py::PhraseWalk::test_team`, `::test_strict` | integration | states 1 to 6 hold on a core-only repo and with a profile set by phrase |
| AC-17 | `tests/test_cli.py::Docs::test_scaffold_explains_auto_mode` | unit | the scaffold README text, and no `defaultMode` in the scaffold settings |
| AC-18 | `tests/test_setup.py::NoSandbox::test_docs_offer_the_recipe_not_a_sandbox`, `tests/test_cli.py::Docs::test_setup_skill_asks_for_the_phrase`, `::test_skills_name_where_and_with`, `::test_skills_name_the_part_they_need`, `::test_docs_document_where_and_with` | unit | the recipe and the skills reach `solo` with the phrase; `sdlc where` and `--with` are documented |
| AC-19 | `tests/test_shell_hooks.py` (version assertion), `tests/test_cli.py::Feedback::test_prints_links_offline` (README pins), `tests/test_rules.py::History::test_current_scaffold_in_history`, `tests/test_cli.py::Docs::test_changelog_has_the_release`; `make check`, `make validate` | unit | version, pins, CHANGELOG and scaffold history agree on 0.2.0-alpha.4 |
| AC-20 | `tests/test_cli.py::InitParts::test_rerun_after_partial_core_setup_stays_core`, `::test_rerun_after_partial_with_maintain_completes_it` | integration | a rerun after a setup that stopped part-way installs what the first run chose |
| AC-21 | `tests/test_cli.py::Docs::test_profile_eval_case_is_complete`; `make evals` (case `profile-by-phrase`) | unit + e2e | the case is complete and listed; the agent leaves the config alone and asks for the phrase |

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
| 2026-11-11 | S11 | `make evals` was not run as planned. With the Bash grant the eval tool refuses every run on this machine ("sandbox required but unavailable … socat not installed"; an API key was not the obstacle). The single case ran with `--case profile-by-phrase --runs 1 --allow-tools Write Edit`: with the plugin 1.00 (asks-for-phrase PASS ×3, config-unchanged ✓), without 0.50 (asks-for-phrase FAIL ×3), Δ +0.50, $0.23 | Installing `socat` needs sudo, which is the human's. Left to the human before the merge: `sudo apt install socat`, then `make evals`, for the run with Bash that AC-21 names | S11 |
