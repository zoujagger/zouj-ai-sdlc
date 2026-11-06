---
id: 0005
title: Close the shell-write guard gaps found in the 0004 reviews
status: Approved
spec: ./spec.md
created: 2026-11-06
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-06T13:52:35Z
approved-via: cli
approved-sha256: bccf6c53a8475d1b5b67e296db075b8e40947ad4cd6ded363b5adbe59b210f2c
---

# Plan: Close the shell-write guard gaps found in the 0004 reviews

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Every change adds blocks, so the order runs from the smallest and most local change to the widest:
1. the registry and `guard-bash` regexes (gap 3)
2. the allowance rule (gap 6)
3. the shared lock-env helper (gap 5)
4. the safety pass in repos without `.aiops/` (gap 2)
5. the protected-tree check for deletes (gap 1)
6. incoming changes: archives first, then git (gap 4)

Each step registers the ids it emits, in the same commit, so `tests/test_rules.py::Coverage` stays green. A final
step proves the playbook and the existing suite (AC-12, AC-13), then the docs follow.

Spec-gate decisions (zoujagger, 2026-11-06):
- `git pull` is refused off main, with the procedure fetch then merge
- deleting a directory that holds a tracked secret is blocked

Plan decisions (zoujagger, 2026-11-06):
- **One PR** for S1-S9, with one fresh-context review.
- **S8's Red evidence** is a planted, reverted break, recorded in the commit message; no permanent mutation test.
- **The safety pass's extra python start** in repos without `.aiops/` is accepted, with no time budget in the tests.
  It's documented in the CHANGELOG.

Code to reuse:
- `guards._check_command` (`guards.py:674`): the target loop, `_rel`, `_aiops_protected`, `glob_hit`, `globs`
- the parent-directory test already in the git branch (`guards.py:~760`, `g.startswith(r.rstrip("/") + "/")`)
- `guards._extract_dirs` (`guards.py:559`), `_git_sub` (`:344`), `_git_config_writes_signing` (`:587`),
  `_toolchain_path` (`:630`), `_in_plugin` (`:661`)
- `cli.init_actions` (`cli.py:429`) → `_agent_blocked`
- `lifecycle.agent_may_write` / `LOCK_ENV`
- `rules.dumps_environment` → `rules.safe_env_command`
- `hooks/engine.sh:12` (the `.aiops` early exit)
- test fixtures: `tests/helpers.RepoCase`, the `test_guards.Ids` helpers, `test_shell_hooks.Allowance`,
  `test_playbook.Playbook`

## Steps
- [x] **S1**: Environment dumps (gap 3) and the registry stages.
  - `re_dump_env` tests `$u` with an optional path prefix: `${S}(\S*/)?(printenv|env)${E}`.
  - New `re_environ='/proc/[^ ;&|]*/environ'` → `block G-ENV-05` (secret).
  - `defaults/rules` adds G-ENV-05. The stage of G-SEC-01, G-TOOL-02, G-TOOL-04, G-TOOL-05 and G-BASH-01 becomes
    `every-repo`; `rules.md` adds a G-ENV-05 section.
  - Files: `hooks/guard-bash.sh`, `defaults/rules`, `defaults/rules.md` (modify).
  - Test first: `tests/test_shell_hooks.py::EnvSpellings::test_spellings_are_dumps` (`/usr/bin/env`, `e''nv`,
    `"printenv"`, `\env` → G-ENV-03; `cat /proc/self/environ`, `xargs -0 < /proc/1/environ` → G-ENV-05) and
    `tests/test_rules.py::Why::test_safety_rules_every_repo` (G-SEC-01, G-TOOL-02, G-TOOL-04, G-TOOL-05, G-BASH-01
    → "in every repo"). They fail on today's regex and stages.
  - Covers: AC-4, AC-11
- [x] **S2**: G-ENV-03 allowances accept only safe forms (gap 6).
  - `rules.safe_env_command(cmd)` (R-6 rules); `allowed()` requires it for G-ENV-03.
  - `allowance_problems` reports others: "G-ENV-03 allows only `printenv NAME…` or a command that doesn't run
    env/printenv".
  - `dumps_environment` becomes `return not safe_env_command(cmd)` (alias, one release).
  - Files: `lib/sdlc_engine/rules.py` (modify).
  - Test first: `tests/test_rules.py::Allowance::test_only_safe_env_forms` with AC-10's accepted and refused lists,
    and `tests/test_shell_hooks.py::Allowance::test_safe_env_forms_through_the_hook` (`ls env` allowed with an
    entry; `bash -c env` and `env env` blocked with one). They fail: today `bash -c env`, `env env`,
    `if true; then env; fi`, `env FOO=1 make` and `watch env` are accepted.
  - Covers: AC-10
- [x] **S3**: The lock is judged without the agent's env, for `init --force` too (gap 5).
  - `machine.lock_env_stripped()` (a context manager that pops `SDLC_HOOK_PROFILE` and `AIOPS_INTENT`).
  - `lifecycle.agent_may_write` uses it (no behaviour change there), and `cli.init_actions(agent=True)` wraps
    `_agent_blocked` in it.
  - Files: `lib/sdlc_engine/machine.py`, `lib/sdlc_engine/cli.py`, `lib/sdlc_engine/lifecycle.py` (modify).
  - Test first: `tests/test_cli.py::Init::test_agent_force_ignores_lock_env`. A locked repo with a modified
    Makefile; `CLAUDECODE=1 SDLC_HOOK_PROFILE=spike sdlc init --force` (and `AIOPS_INTENT=0009`) keeps the Makefile
    and lists it. It fails today: the Makefile is overwritten.
  - Covers: AC-9
- [x] **S4**: A safety pass in repos without `.aiops/` (gap 2).
  - `hooks/engine.sh` skips the early exit for `pre-bash` (and still prints nothing for `session-start` and
    `prompt`).
  - `check_bash`: in an uninitialized repo, run `_check_command(…, gates=False)`.
  - `_check_command` gains `gates`; with it False, only the plugin, outside-repo secret and toolchain checks run,
    plus `_git_config_writes_signing` for `--global`/`--system`/`-f <outside>`, and nesting.
  - Files: `hooks/engine.sh`, `lib/sdlc_engine/guards.py` (modify).
  - Test first: `tests/test_guards.py::Uninitialized::test_safety_pass_blocks` (AC-3 commands → G-TOOL-04, G-SEC-01,
    G-TOOL-02, G-TOOL-05, plus a `bash -c` nesting) and `::test_gates_stay_dormant` (`rm -rf src`,
    `echo x > src/a.py`, `git push origin main` allowed), driven through `hooks/engine.sh pre-bash` in a repo with
    no `.aiops/`. They fail today: every command passes.
  - Covers: AC-3
- [x] **S5**: Deleting a protected tree (gap 1).
  - `guards._contains_protected(root, target, cwd)`: the repo root or an ancestor; `.aiops`, `.git`; protected-glob
    prefixes; `git ls-files -z -- <target>` matched against the protected and secret globs.
  - It's called for the delete and move targets (`rm`, `rmdir`, `unlink`, `shred`, `mv` sources, `find … -delete`
    roots) in every state. It blocks G-FILE-05 (gate), or the existing `.aiops` id for `.aiops`.
  - `defaults/rules` and `rules.md` add G-FILE-05.
  - Files: `lib/sdlc_engine/guards.py`, `defaults/rules`, `defaults/rules.md` (modify).
  - Test first: `tests/test_guards.py::ProtectedTree`, failing today because these pass in state 4:
    - `test_blocks_in_unlocked_state`: the AC-1 commands
    - `test_allows_ordinary_deletes`: the AC-2 commands, with a 10 000-file untracked `node_modules` timed under
      200 ms
    - `test_tracked_secret_dir`: `rm -rf config` with a committed `config/prod.key`
  - Covers: AC-1, AC-2
- [x] **S6**: Archives can't bring in protected config (gap 4, part 1).
  - `guards._incoming_paths` for `tar -x` / `unzip` into the repo: `tarfile` / `zipfile` member names, joined with
    the extract dir.
  - A member under `.aiops/config*`, `.claude/settings.json` or a protected path is G-FILE-06. An unreadable or
    missing archive is G-FILE-06 too ("can't inspect").
  - `defaults/rules` and `rules.md` add G-FILE-06.
  - Files: `lib/sdlc_engine/guards.py`, `defaults/rules`, `defaults/rules.md` (modify).
  - Test first: `tests/test_guards.py::Incoming::test_archives`: tar.gz and zip carrying
    `.aiops/config/allowed-commands`, `.claude/settings.json` or `.github/workflows/aiops-gates.yml` are blocked; a
    `src/`-only archive is allowed; a missing archive is refused. It fails today: extraction into `.` passes.
  - Covers: AC-5
- [x] **S7**: Git can't bring in protected config (gap 4, part 2).
  - `git stash pop|apply`: `git stash show --name-only --include-untracked`.
  - `git merge|rebase <ref>`: `git diff --name-only HEAD...<ref>`. `git cherry-pick <c>`: `git show --name-only`.
  - The main branch and `origin/<main>` are exempt, and so are paths under `.aiops/NNNN-*`.
  - `git pull` is refused off the main branch (G-FILE-06, procedure: "git fetch, then git merge <ref>").
  - Files: `lib/sdlc_engine/guards.py` (modify).
  - Test first: `tests/test_guards.py::Incoming`, failing today because each of these passes in state 4:
    - `test_stash`: a stash changing `.aiops/config/protected-paths` is blocked; a `src/` stash is allowed
    - `test_merge_rebase_cherry_pick`: branch `x` changing `.aiops/config.json` is blocked; `main`, `origin/main`
      and an approval-only branch are allowed
    - `test_pull`: refused on a feature branch, allowed on main
  - Covers: AC-6, AC-7, AC-8
- [x] **S8**: Playbook conformance and the existing suite.
  - `test_playbook.Playbook.walk` asserts each AC-1 command stays blocked in states 1, 4 and 5, in all three
    profiles.
  - Fix any existing test that a new block catches only if the command really is unsafe; otherwise narrow the
    check. Log either case.
  - Files: `tests/test_playbook.py` (modify); guards only if a regression appears.
  - Test first: the new walk assertions, written before any fix S8 needs. With S1-S7 correct they pass on the first
    run, and the Red evidence is a planted `_contains_protected → None` run, recorded in the commit message.
  - Covers: AC-12, AC-13
- [x] **S9**: Docs.
  - `docs/architecture.md`: the always-on safety row, `.aiops/` integrity (parent directories, incoming changes),
    the static-parsing residuals, and the "Safety off in unrelated repos" residual removed.
  - `README.md`: always-on guards; `git pull` off main.
  - `TROUBLESHOOTING.md`: G-FILE-05, G-FILE-06, and "fetch then merge".
  - CHANGELOG `[Unreleased]` (planned as 0.2.0-alpha.4): Security fixes, and the matching 0.2.0-alpha.3 known
    issues marked fixed. `docs/roadmap.md`: a line on 0005.
  - Files: `docs/architecture.md`, `README.md`, `TROUBLESHOOTING.md`, `CHANGELOG.md`, `docs/roadmap.md` (modify).
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_docs_match_what_shipped` gains an assertion that
    architecture.md no longer says "aren't checked in a repo without `.aiops/`". It fails until the doc is updated.
  - Covers: AC-13

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| R-1 blocks common deletes (`rm -rf build`, `dist`, `node_modules`) | medium | high | Only tracked files and protected-glob prefixes count, so untracked trees aren't walked. AC-2 lists commands that must stay allowed, with a timing budget |
| Safety pass in uninitialized repos is slow or crashes unrelated work | medium | medium | One python start like the secret scan; `gates=False` skips git calls. engine.sh's fail-closed applies only to `pre-*` and blocks on an engine crash, so the Uninitialized tests guard against crashes |
| Refusing `git pull` off main disrupts the agent | high | low | The block procedure says exactly what to do (fetch + an inspected merge); pull on main stays allowed |
| `git diff HEAD...<ref>` with an unknown ref, or a shallow clone | medium | low | Can't tell → refuse with the procedure (fetch the ref); tested |
| Approval commits from a clean clone are blocked by R-4 | low | high | `.aiops/NNNN-*` paths exempt; the approval-only branch test in S7 |
| Archive inspection of huge or malicious archives (zip bombs, absolute or `..` member names) | low | medium | Only member *names* are read, never content. Absolute and `..` names count as outside, and are refused if they land in the repo |
| Existing tests rely on now-blocked commands | medium | low | S8 runs the whole suite; each case is fixed or the check narrowed, and logged |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_guards.py::ProtectedTree::test_blocks_in_unlocked_state`, `::test_tracked_secret_dir` | integration | root, ancestors, `.aiops`, `.git`, protected trees and tracked-secret dirs can't be deleted or moved in state 4 |
| AC-2 | `tests/test_guards.py::ProtectedTree::test_allows_ordinary_deletes` | integration | ordinary deletes, copies and moves stay allowed; `node_modules` decided within 200 ms |
| AC-3 | `tests/test_guards.py::Uninitialized::test_safety_pass_blocks`, `::test_gates_stay_dormant` | integration | toolchain, plugin and secret shell writes blocked without `.aiops/`; gates dormant |
| AC-4 | `tests/test_shell_hooks.py::EnvSpellings::test_spellings_are_dumps` | unit | every env spelling is G-ENV-03; `/proc/*/environ` is G-ENV-05 |
| AC-5 | `tests/test_guards.py::Incoming::test_archives` | integration | archives carrying protected config are refused; plain archives allowed; an unreadable one refused |
| AC-6 | `tests/test_guards.py::Incoming::test_stash` | integration | a stash bringing protected config is refused |
| AC-7 | `tests/test_guards.py::Incoming::test_merge_rebase_cherry_pick` | integration | merge, rebase and cherry-pick of protected config are refused; main and approval-only branches allowed |
| AC-8 | `tests/test_guards.py::Incoming::test_pull` | integration | pull refused off main with the fetch+merge procedure; allowed on main |
| AC-9 | `tests/test_cli.py::Init::test_agent_force_ignores_lock_env` | integration | the agent's `init --force` can't lift the lock with env |
| AC-10 | `tests/test_rules.py::Allowance::test_only_safe_env_forms`, `tests/test_shell_hooks.py::Allowance::test_safe_env_forms_through_the_hook` | unit | only `printenv NAME…` and non-running forms are allowable |
| AC-11 | `tests/test_rules.py::Why::test_safety_rules_every_repo`, `tests/test_rules.py::Coverage::*` | unit | new ids registered and emitted; stages accurate |
| AC-12 | `tests/test_playbook.py::Playbook::test_solo`, `::test_team`, `::test_strict` | e2e | AC-1 commands stay blocked across the walk in every profile |
| AC-13 | the whole suite (`make check`), `tests/test_shell_hooks.py::ShellHooks::test_docs_match_what_shipped` | regression | nothing previously allowed is newly blocked without a logged reason; docs match |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-06 | S5 | Two additions. **Home and its ancestors are protected too:** deleting `~` takes `~/.ssh`, the global git config and the installed plugin, whether or not the repo is under home. **`find … -delete` counts as a tree delete only without a filter** (`-name`, `-path`, `-type`, …): a filtered find deletes matching files only, and the existing G-ART-04 still protects `.aiops/` from it. | A home-delete is catastrophic in every repo layout. `find . -name '*.pyc' -delete` is a common, safe command that existing tests rely on. | S5 |
| 2026-11-06 | S6 | An archive that can't be read is refused only when the extract directory is the repo root or holds `.aiops/`, `.claude/` or a protected path; elsewhere (`-C build`) it's allowed. AC-5's "an unreadable archive is refused" holds for extraction into the repo root, which the test uses. | GNU tar and unzip drop `..` members, so such an archive can only write under its destination. Three existing tests extract into `build/` (AC-13). | S6 |
| 2026-11-06 | review r1 | **Scope (zoujagger, 2026-11-06):** every bypass of the six gaps and every false positive found in review round 1 is fixed here, plus the wrapper-prefix hole (already on main), which voids all of 0005. The other older classes go to a new intent 0006: git plumbing (`update-index`, `checkout-index`, `read-tree`), `switch`/`checkout <branch>`/`reset`/`revert`, `export`/`declare`/`set`/`ps` dumps, case-insensitive filesystems, human-only checks in uninitialized repos. | Round 1: CHANGES_REQUESTED 62/100 (security FAIL, 6 HIGH). | 3e31fff, a252209 |
| 2026-11-06 | review r1 | Fixes:<br>- **G-ENV-03:** back to matching on `$c` as on main (no quoted-`env` false positives), plus a command-position match on `$u` with any path prefix. This replaces S1's bin-dir-only prefix, which wasn't logged.<br>- **G-ENV-05:** catches `/proc` globs and `cd /proc`.<br>- **Wrappers:** stripped with their options and operands.<br>- **Safety pass:** secret and toolchain checks on every target (a `$HOME` session root); `git config` scope by option prefix, `-f` outside the repo, `GIT_CONFIG*=` (S4's planned `-f`, missed before); copies and extractions into home or toolchain directories.<br>- **`git pull` on main:** only a pull of main itself.<br>- **G-FILE-06:** every operand, value options, cherry-pick ranges, `stash branch`, `-z`; archives with `--strip-components`, `--transform`, `-P`, link members, and resolved through repo symlinks; `tar xfz` parsing.<br>- **G-FILE-05:** a filtered find judged by the protected files it reaches; `-exec rm`; `pushd`/`popd`; `ln -s` in the same command; `rm link` allowed; `rsync --delete`.<br>- **Safe forms:** every simple command must be safe; `source`/`.` dropped (AC-10 listed `source env/bin/activate` as accepted: it runs its argument, and G-ENV-03 never blocks it anyway); secret-named `printenv` refused. | Review round 1 findings. | 3e31fff, a252209 |
| 2026-11-06 | — | Not logged before:<br>- The S2 test change for `env FOO=1 make`: refused, as R-6 says.<br>- The planned `Why::test_safety_rules_every_repo` was named `Stages0005`.<br>- S6's incoming guard also covers `.aiops/install-state.json` (engine-written, like config).<br>- S9 asserts "only in initialized repos", not the planned wording.<br>- S9 adds a `[Unreleased]` "fixes the 0.2.0-alpha.3 known issues" line instead of editing the released section.<br>- `.env` writes in repos without `.aiops/` are now blocked (G-SEC-01): S4's dormancy test had listed them as allowed. | CLAUDE.md rule 6 (code review LOW). Released notes stay as shipped. | — |
