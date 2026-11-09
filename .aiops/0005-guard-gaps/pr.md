<!-- PR description for intent 0005, generated in state 5. `gh pr create --body-file` it. -->
## Close the shell-write guard gaps found in the 0004 reviews

**Intent:** `.aiops/0005-guard-gaps/` ([intent](intent.md) · [spec](spec.md) · [plan](plan.md) · [review](review.md))
**Review:** PASS (under zoujagger's stop rule), 82/100 at `eea6268`

### What and why
The 0004 security reviews found six ways a shell command gets past the guards or past an allowance. All of them
predate this intent. This PR closes them:
- **Protected trees can't be deleted (G-FILE-05).** This covers the repo itself, directories above it or above home,
  and directories holding `.aiops/`, `.git/`, a protected path or a tracked secret.
- **Repos without `.aiops/` get a safety pass.** Shell writes to the approval toolchain, the installed plugin and
  secrets outside the repo are blocked in every repo. SDLC gates stay dormant.
- **Every spelling of an environment dump is caught.** That includes `/usr/bin/env`, `e''nv` and `\env`. Reading
  `/proc/*/environ` is the new rule G-ENV-05.
- **Protected config can't be brought in from elsewhere (G-FILE-06).** This applies to archives, `git stash
  pop|apply`, `git merge|rebase|cherry-pick` and `git pull`; main and approval commits pass. `git pull` off main is
  refused: run `git fetch`, then `git merge <ref>`.
- **The agent's `init --force` judges the lock without `SDLC_HOOK_PROFILE` / `AIOPS_INTENT`.**
- **G-ENV-03 allowances accept only safe forms.**

Nine review rounds also made the shared shell parser, used by the guards and the always-on secret scan, read
commands closer to bash. The changes:
- comments
- heredoc delimiters as bash words
- line continuations
- `$'…'`
- `)>`
- `!`/`{` in command position
- `time -p`
- only the real `case` keywords
- wrapper prefixes

Each refinement over the old parse is an extra reading that only adds blocks.

### Acceptance criteria
- [x] AC-1: protected-tree deletes are blocked in state 4 with the exact id (`tests/test_guards.py::ProtectedTree::test_blocks_in_unlocked_state`)
- [x] AC-2: ordinary deletes are allowed, and the check is fast (`::ProtectedTree::test_allows_ordinary_deletes`)
- [x] AC-3: the safety pass runs in repos without `.aiops/` (`::Uninitialized::test_safety_pass_blocks`, `::SafetyPassFuzz`)
- [x] AC-4: every env-dump spelling is caught (`tests/test_shell_hooks.py::EnvSpellings::test_spellings_are_dumps`)
- [x] AC-5: archives are judged by their member names (`tests/test_guards.py::Incoming::test_archives`)
- [x] AC-6: stash pop/apply is inspected (`::Incoming::test_stash`)
- [x] AC-7: merge, rebase and cherry-pick are inspected; main passes (`::Incoming::test_merge_rebase_cherry_pick`, `::IncomingRound6`)
- [x] AC-8: `git pull` is refused off main (`::Incoming::test_pull`)
- [x] AC-9: the agent's `init --force` ignores the lock env (`tests/test_cli.py::Init::test_agent_force_ignores_lock_env`)
- [x] AC-10: G-ENV-03 allowances accept only safe forms (`tests/test_rules.py::Allowance::test_only_safe_env_forms`)
- [x] AC-11: the rules are registered with their stages (`tests/test_rules.py::Stages0005`, `::Coverage`)
- [x] AC-12: the playbook walk keeps protected trees blocked in every state and profile (`tests/test_playbook.py`)
- [x] AC-13: the full suite is green (342 tests), with no known regression against main

### Deviations from plan
These are logged in the plan's Deviation log, with SHAs:
- **Scope widened in review round 1 (zoujagger).** Every bypass and false positive found in review is fixed here,
  plus the wrapper-prefix hole that was already on main.
- **AC-10:** `source env/bin/activate` is refused rather than accepted, because `source` runs its argument.
- **AC-2:** the 200 ms limit is asserted in process; the whole hook call is held to under 2 s.
- **Two checks are looser than main:** `find . -type d -delete` (it removes only empty directories) and
  `git cherry-pick` of a commit already on main are allowed.
- **Subshell scoping was reverted (zoujagger, round 9).** A subshell's `cd` and assignments persist past `)`, exactly
  as on main. Four review rounds each defeated exact scoping with a `)` that bash keeps inside a word.

### Known residuals, deferred to intent 0006
These are listed in `docs/architecture.md`:
- exact subshell scoping
- `)#<<EOF`
- `true&&>/dev/null cmd`
- `$'…'` heredoc delimiters
- assignments in pipelines, `&` jobs and conditional branches
- a `#` with a quote nested in `"$(…)"`
- the intent-0006 git and download forms already listed there

The local guards are a deterrent. The signed-approval CI audit is the hard guarantee.

### Risks and rollback
- **Release:** ships as **0.2.0-alpha.4**. The CHANGELOG stays under `[Unreleased]` until the release PR.
- **Rollback:** reinstall 0.2.0-alpha.3. Nothing is stored, so there is nothing to migrate.
- **Watch:** false-positive reports that quote G-FILE-05 or G-FILE-06 (issue template `quick-feedback`).
- **Highest-risk code:** this branch adds about 1000 lines to the shell parser (`lib/sdlc_engine/shell.py`). Every
  regression the review rounds found came from there.
- **Not re-reviewed:** the final scoping revert (`eea6268`) removes code so that the guard matches main's reading.
  No reviewer looked at it independently.

### Human decision
The agent does not merge. A CODEOWNER reviews and decides.
