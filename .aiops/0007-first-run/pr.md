<!-- PR description for intent 0007, generated in state 5. `gh pr create --body-file` it. -->
## First run in five minutes (profile by phrase, terminal command, core scaffold)

**Intent:** `.aiops/0007-first-run/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS, 88/100 at `ccef62e` (round 2; round 1 was PASS 86/100, and its one MEDIUM was fixed first)

### What and why
A newcomer on 0.2.0-alpha.3 couldn't finish the guided setup inside Claude Code. The profile they picked became a
terminal step, the terminal command was hard to find, and the scaffold added workflows for stages they hadn't
reached. This PR adds:
- **Profile by phrase.** The human types `Setup Profile solo|team|strict` as the whole prompt. The prompt hook sets
  the repo's first profile in `.aiops/config.json` and commits that file alone, unsigned, with `AIOps-Profile:` and
  `Set-By:` trailers. It works only while the config is the untouched template and nothing is approved, in the
  files or the history. The agent still can't choose a profile, and a later change stays a terminal run
  ([ADR 0003](../../docs/adr/0003-first-profile-by-typed-phrase.md)).
- **`sdlc where`.** It prints the command for the human's own terminal, and the status card shows it when a human
  step is pending.
- **A core scaffold.** `setup` and `init` write the 16 core files by default. Five opt-in parts (`review`,
  `maintain`, `deploy`, `governance`, `issues`) come with `--with`. Install-state records the choice, and the
  lifecycle commands respect it.
- **Auto mode docs** for state 4 in the scaffold's `.aiops/README.md`.

It ships with intent 0005 as **0.2.0-alpha.4**.

**Reading the diff:** commit `7d8d4d0` is a style-only `ruff format` of `lib/` and `tests/` (+5123/−2069). For the
feature alone, read `git diff origin/main 87d3ac8` plus `git show ccef62e`.

### Acceptance criteria
- [x] AC-1: the phrase sets the first profile and commits the config alone (`tests/test_setup.py::FirstProfile::test_sets_and_commits_config_alone`, `tests/test_cli.py::ProfilePhrase::test_whole_prompt_sets_the_profile`)
- [x] AC-2: approvals then go through the hook with no terminal step (`tests/test_playbook.py::PhraseWalk::test_solo`)
- [x] AC-3: refused when a profile is set, the config was edited, or something was approved, in the files or the history (`tests/test_setup.py::FirstProfile::test_refused_*`)
- [x] AC-4: phrase inside other text is ignored; unknown names list the profiles (`tests/test_cli.py::ProfilePhrase`)
- [x] AC-5: dormant without `.aiops/` (`tests/test_cli.py::ProfilePhrase::test_dormant_without_aiops`)
- [x] AC-6: works with the session markers set (`tests/test_cli.py::ProfilePhrase::test_works_with_the_session_markers_set`)
- [x] AC-7: the agent's setup, Write and shell writes still can't change the config (`tests/test_cli.py::ProfilePhrase::test_agent_setup_and_writes_still_cannot_change_config`)
- [x] AC-8: team and strict replies carry the signing and CODEOWNERS steps (`tests/test_setup.py::FirstProfile`)
- [x] AC-9: `sdlc where` prints the terminal command anywhere (`tests/test_cli.py::Where`)
- [x] AC-10: the card shows the terminal line when a human step is pending (`tests/test_cli.py::Card`)
- [x] AC-11: a fresh setup or init writes the 16 core files, with no schedule and no secret (`tests/test_cli.py::InitParts`, `tests/test_setup.py::Parts`)
- [x] AC-12: `--with <part>` adds only that part (`tests/test_cli.py::InitParts`, `tests/test_setup.py::Parts`)
- [x] AC-13: lifecycle commands on a core-only repo don't offer opt-in files (`tests/test_lifecycle.py::CoreOnly`)
- [x] AC-14: alpha.3 install-state reads as every part (`tests/test_lifecycle.py::Compat`, `tests/test_cli.py::InitParts`)
- [x] AC-15: every scaffold file belongs to exactly one part (`tests/test_lifecycle.py::Parts`)
- [x] AC-16: the playbook walk holds on core in every profile, also by phrase (`tests/test_playbook.py::CoreWalk`, `PhraseWalk`)
- [x] AC-17: the scaffold explains auto mode (`tests/test_cli.py::Docs::test_scaffold_explains_auto_mode`)
- [x] AC-18: the docs and skills offer the phrase, `where` and `--with` (`tests/test_cli.py::Docs`, `tests/test_setup.py::NoSandbox`)
- [x] AC-19: release 0.2.0-alpha.4 (`tests/test_cli.py::Docs::test_changelog_has_the_release`, `make validate`)
- [x] AC-20: a rerun after a partial setup completes what the first run chose (`tests/test_cli.py::InitParts`, `tests/test_setup.py::Parts`)
- [x] AC-21: eval case `profile-by-phrase` (`tests/test_cli.py::Docs::test_profile_eval_case_is_complete`). In `make evals` it scored 1.00 with the plugin; on its own, 1.00 with the plugin vs 0.83 without (quoted in review.md)

### Deviations from plan
The plan's Deviation log has 24 rows. The main ones:
- **S2:** "on disk" means byte-equal to a released file. 22 existing init tests now pass `--with all`.
- **S5 / S7:** the engine changed more than planned. `config_written` is used, and the "type `Setup Profile <p>`"
  step is printed for every profile, `team` included.
- **S8:** at a gate, the card's terminal line is the full approve command.
- **S11:** `make evals` needed `socat`, which the human installed. The full run was stopped at 6 of 7 cases;
  `intent-first` scored 0.89, an older issue.
- **S12:** main was merged into the branch instead of rebasing it, to keep the signed approval commits.
- **Review r1:**
  - A style-only `ruff format` commit. It leaves `bin/sdlc` out of `make format`, because ruff broke its sh/python
    header.
  - The history check that closes the round 1 MEDIUM.

### Risks and rollback
- **No migration.** Install-state without `parts` reads as every part, and no existing repo's files change.
- **Accepted residual.** An agent that starts its own session (`claude -p "Setup Profile solo"`) can set the
  profile in a repo with the template config and nothing approved. It leaves a visible commit, and CI reads the
  config from the base branch. Recorded in `docs/architecture.md` Known gaps.
- **Open review findings, none blocking:**
  - M1: the card line is missing at a passphrase-key gate.
  - L1: a terminal `setup --profile team` on a new config writes nothing.
  - LOWs:
    - the reflog/branch-deletion path past the history check
    - R-2 condition 1 (the session's repo) isn't enforced
    - the `--with` wording in the threat model
    - the eval grader is weak
    - `git log` runs on every status call
- **Before the merge:** run the phrase by hand once in a `make dev` session (S7), and check `gh pr checks`, because
  shellcheck didn't run locally.
- **After the merge:** tag `v0.2.0-alpha.4` on the merge commit. Until then the README's pin doesn't resolve.
- **Rollback:** revert the PR.
  - A profile set by phrase stays a valid `config.json`.
  - An alpha.3 engine ignores `parts`, lists the left-out parts' files as `new`, and its `upgrade` would offer to
    create them.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
