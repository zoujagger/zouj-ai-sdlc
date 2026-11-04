---
id: 0003
title: Guided setup and first-run onboarding (roadmap phase 1)
status: Approved
spec: ./spec.md
created: 2026-11-03
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-04T12:41:32Z
approved-via: cli
approved-sha256: 27ea9e8c60e785c34a1bb9a0d1e84299f13f7745c6356e868bfd53e047983924
---

# Plan: Guided setup and first-run onboarding (roadmap phase 1)

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Build from the inside out, so every user-facing piece rests on tested engine parts:
1. **One source of truth for the scaffold.**
   - Split `cmd_init` (`lib/sdlc_engine/cli.py:297-340`) into `init_actions(root, stack)`, which returns the planned
     create/skip actions, and `apply_init(...)`.
   - `init` and `setup` both use it, so the two can't drift.
2. **Policy pieces in the engine.**
   - The `"sk"` key policy, next to `"human"` in `approvals.signing_problem` (`approvals.py:183`). It reuses
     `key_protection` and `_signer_options`.
   - The `profile` key in config, read through `machine.config` (`machine.py:59`) with a default of `team`.
   - Doctor rows for the profile and for strict CODEOWNERS, in `cli.cmd_doctor` (`cli.py:370`).
3. **`lib/sdlc_engine/setup.py`** (new, stdlib only): preflight → inventory → plan → (confirm) → apply → human
   steps → doctor.
   - External tools (`claude`, `gh`, `git config credential.helper`) are found through `shutil.which` and run with
     a short timeout. Tests drive them with stub executables on PATH.
   - Under the agent (`approvals.running_under_agent()`), human-owned files that already exist are never written
     (spec R-4).
4. **The user-facing pieces:** `feedback`, the skill, docs, and the playbook conformance test, which covers all three
   profiles. (A sandbox was built in S9 and removed in S15 after review round 3.)
5. **The release** comes last.

One spec phrase is interpreted here: "`permissions`/`hooks` byte-identical" (AC-5). The settings merge loads and
dumps JSON with `indent=2`, so whitespace in an existing file may be normalised. The **values** under `permissions`
and `hooks` must stay exactly equal, which the test checks through parsed equality, and no other key may change.
**Stress-test answers (zoujagger, 2026-11-03):**
- **The JSON re-dump is accepted:** values equal, whitespace may be normalised, and the diff is shown first.
- **Preflight tool failures warn and continue:** each call has a 5 s timeout, and its row becomes `!` with the fix.
  Only git, python and make problems stop setup.
- **S12 may be a pin:** if it has no red run, that's logged in the Deviation log.

## Steps
- [x] **S1**: Refactor `cmd_init` into `init_actions` + `apply_init` (no behaviour change)
  - Files: `lib/sdlc_engine/cli.py` (modify)
  - Test first: `tests/test_setup.py::Init::test_init_actions_preview_matches_apply`. `init_actions` lists exactly the
    files a following `sdlc init` creates or keeps. Red: `init_actions` doesn't exist yet.
  - Covers: AC-1 (shared preview), AC-3
- [x] **S2**: Marketplace snippet in the scaffold
  - Files: `templates/scaffold/.claude/settings.json` (modify)
  - Test first: `tests/test_cli.py::Init::test_scaffold_offers_the_plugin`. After `init`, settings has
    `extraKnownMarketplaces.zouj.source = {source: github, repo: zoujagger/zouj-ai-sdlc}` and
    `enabledPlugins["zouj-ai-sdlc@zouj"] = true`, and the `permissions.deny` list is unchanged. Red: the keys are
    missing.
  - Covers: AC-9
- [x] **S3**: The `"sk"` key policy and `profile` in config
  - Files: `lib/sdlc_engine/approvals.py`, `lib/sdlc_engine/machine.py`, `lib/sdlc_engine/cli.py` (doctor profile
    row, refusing unknown policies) (modify)
  - Test first: `tests/test_engine.py::Approvals::test_strict_policy_requires_a_touch_key`. Under `"sk"`, a
    passphrase key is refused, an `sk-` key with `no-touch-required` is refused, an `sk-` key with touch passes, and
    doctor refuses `"approval_key_policy": "bogus"`. Red: `"sk"` is treated like `"any"`.
  - Covers: AC-7
- [x] **S4**: Strict requires CODEOWNERS on `.aiops/`
  - Files: `lib/sdlc_engine/cli.py` (doctor) (modify)
  - Test first: `tests/test_cli.py::Lifecycle::test_strict_requires_codeowners`. With `profile: strict` and
    CODEOWNERS not covering `/.aiops/`, the row is ✗ and doctor exits 1. Under `team` it's only `!`. Red: there's no
    such row.
  - Covers: AC-15
- [x] **S5**: Setup preflight
  - Files: `lib/sdlc_engine/setup.py` (create), `lib/sdlc_engine/cli.py` (`setup` in COMMANDS) (modify)
  - Test first: `tests/test_setup.py::Preflight::test_rows_and_blocking`, with stub `claude`, `gh` and `git` on PATH:
    - a missing `workflow` scope gives `!` plus `gh auth refresh -h github.com -s workflow`
    - no credential helper gives `!` plus the gh helper command
    - an old `claude` (2.0) gives `!`
    - `git` missing from PATH, or python < 3.9 (simulated), gives `✗`, and setup stops before writing
    - gh is never called with `-t`/`--show-token`

    Red: there's no `setup` command.
  - Covers: AC-11
- [x] **S6**: Inventory, plan, gate summary, `--dry-run`, and non-tty without `--yes`
  - Files: `lib/sdlc_engine/setup.py` (modify)
  - Test first: `tests/test_setup.py::Plan::test_dry_run_writes_nothing` and `::test_no_tty_needs_yes`:
    - `--profile team --dry-run` prints Preflight, Inventory, Plan (`+` lines) and Gates sections, and leaves
      `git status` clean
    - without `--yes` and without a tty, it exits 2 listing `--profile`
  - Covers: AC-1, AC-6
- [x] **S7**: Apply on a fresh repo with profiles; rerun is idempotent
  - Files: `lib/sdlc_engine/setup.py` (modify)
  - Test first: `tests/test_setup.py::Apply::test_fresh_repo_each_profile` and `::test_rerun_plans_nothing`:
    - for solo, team and strict, `--yes` initializes the repo and writes the profile's config values
    - `sdlc status` shows no active intent, and code is read-only
    - the human steps list the signing commands (team, strict), the CODEOWNERS line (strict) and the `/plugin`
      commands
    - a second run plans 0 writes, and the file mtimes are unchanged
  - Covers: AC-2, AC-3
- [x] **S8**: Human-owned files: the agent vs the human
  - Files: `lib/sdlc_engine/setup.py` (modify)
  - Test first: `tests/test_setup.py::Owned::test_agent_never_writes_existing_owned_files` and
    `::test_human_merges_only_marketplace_keys`, on a repo initialized like 0.2.0-alpha.1 with a custom settings
    file:
    - under `CLAUDECODE=1`, `config.json` and `settings.json` are unchanged, and the human steps print the keys and
      the profile change
    - as a human with `--yes`, only the two keys are added, `permissions`/`hooks` parse equal, and the profile
      change is shown as a diff and applied
  - Covers: AC-4, AC-5
- [x] **S9**: Sandbox
  - Files: `lib/sdlc_engine/setup.py` (modify), `templates/sandbox/` (create: `src/app.py`, `tests/test_app.py`, the
    `0001` intent text)
  - Test first: `tests/test_setup.py::Sandbox::test_creates_committed_repo`:
    - for a missing dir: a git repo on `main`, a clean tree, the solo scaffold, a Draft `0001` that validates, and
      `make check` green in it
    - the calling repo is unchanged
    - a non-empty dir gives exit 1
    - a symlinked target is refused
  - Covers: AC-10
- [x] **S10**: `sdlc feedback`
  - Files: `lib/sdlc_engine/cli.py` (modify)
  - Test first: `tests/test_setup.py::Feedback::test_prints_links_offline`. It prints the issue-template URLs and the
    doctor summary, exits 0, and `socket.socket` is patched to raise, proving there's no network use. Red: there's
    no command.
  - Covers: AC-13
- [x] **S11**: The `/zouj-ai-sdlc:setup` skill; init points to setup
  - Files: `skills/setup/SKILL.md` (create), `skills/init/SKILL.md` (modify)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_setup_skill_follows_the_playbook`:
    - the skill exists with frontmatter
    - it runs `sdlc setup --dry-run` first
    - it sends human-owned steps to the terminal
    - it never offers a gateless option
    - `skills/init` mentions setup

    Red: the skill is missing.
  - Covers: AC-12 (the skills part)
- [x] **S12**: Playbook conformance test, per profile
  - Files: `tests/test_playbook.py` (create); engine fixes only if a check fails
  - Test first: `tests/test_playbook.py::Playbook::test_<profile>` for solo, team and strict. Each one:
    - inits through `setup --yes`
    - walks states 1 → 6 only through `approvals.approve` (the human path)
    - asserts that pre-bash and pre-edit block code writes in states 1-3, and block the agent's `sdlc approve`,
      `gh pr merge`, `git push origin main` and `make deploy ENV=prod`
    - asserts that state 6 needs a PASS review on main
    - asserts that the Stop hook blocks while `make check` is red

    This may be green at once: it pins existing behaviour across profiles. If so, that's logged as a pin, as S14 was
    in 0002.
  - Covers: AC-8
- [x] **S13**: Task-first docs and support surfaces
  - Files:
    - `README.md` (restructure: a "Start using" table with playbook stages, three pinned install paths, the
      official-sources note)
    - `TROUBLESHOOTING.md`, `COMMANDS-QUICK-REF.md` (create)
    - `.github/ISSUE_TEMPLATE/install-problem.yml`, `quick-feedback.yml`, `config.yml` (create)
    - `docs/roadmap.md` (Phase 1 status)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_onboarding_docs`:
    - the README's first H2 after the title is "Start using", and it shows `sdlc setup`, the two `/plugin` commands
      and the JSON snippet
    - the files exist
    - every `/zouj-ai-sdlc:<name>` in the quick reference is a real `skills/<name>/SKILL.md`
    - the troubleshooting page covers approvals, signing, push scope and blocks

    Red: the files are missing.
  - Covers: AC-12
- [x] **S14**: Release 0.2.0-alpha.2
  - Files: `.claude-plugin/plugin.json`, `CHANGELOG.md`, `tests/test_shell_hooks.py` (version assertion) (modify)
  - Test first: `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog`, asserting
    `0.2.0-alpha.2`. Red: the version is still alpha.1.
  - Covers: AC-14
- [x] **S15**: Remove the sandbox; the README shows a throwaway-repo recipe instead (intent and spec amended
  2026-11-04)
  - Files:
    - `lib/sdlc_engine/setup.py`:
      - The sandbox code is removed: `sandbox`, `_build_sandbox`, `_empty_pinned`, `_same`, `_in_git_work_tree`,
        `SANDBOX`, the `--sandbox` branch of `main`, and `import secrets` if unused.
      - `main` refuses any option it doesn't know (exit 1, naming it and the valid options) before doing anything.
    - `lib/sdlc_engine/cli.py`: the usage line drops `setup --sandbox <dir>`. `_wire_stack`'s recipes-file argument
      goes if nothing else uses it.
    - `templates/sandbox/` (delete)
    - `tests/test_setup.py`: the `Sandbox`, `SandboxRace` and `SandboxRaceDeeper` classes are replaced by
      `NoSandbox`
    - Docs:
      - README: the "Start using" row and "Just looking?" become the throwaway-repo recipe
      - `COMMANDS-QUICK-REF.md`, `skills/setup/SKILL.md` (arguments and step 1)
      - CHANGELOG: the sandbox Added/Security bullets are removed. The section notes that setup refuses unknown
        options and that the README shows how to try the workflow
      - `docs/roadmap.md`: the sandbox is dropped from Phase 1, not moved to a later phase
  - Test first: `tests/test_setup.py::NoSandbox`:
    - `test_unknown_option_refused`: `sdlc setup --sandbox <dir>` and `sdlc setup --bogus` exit 1, name the option,
      create no `<dir>`, and leave `git status` clean
    - `test_docs_offer_the_recipe_not_a_sandbox`: README, quick reference, setup skill and CLI usage don't mention
      `--sandbox`; `templates/sandbox/` doesn't exist; the README has the `git init` + `sdlc setup --profile solo
      --yes` recipe

    Red: setup still builds the sandbox, and the docs still offer it.
  - Covers: AC-10

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The `cmd_init` refactor changes init output or behaviour | medium | high | S1 is a pure refactor with a preview-equals-apply test; existing `tests/test_cli.py::Init` tests must stay green |
| Preflight shells out to `claude`/`gh`: slow, hangs, or prints a token | medium | medium | 5 s timeout per call, never `-t`, output parsed for scopes only, stubbed in tests |
| The settings merge reformats a user's `.claude/settings.json` | medium | low | values parse equal; only the two keys are added; the diff is shown before the human confirms; agent runs never touch it |
| A profile accidentally weakens a gate | low | high | S12 conformance test per profile; profiles map only to `require_signed_approvals`, `commit_approvals` and `approval_key_policy` |
| The sandbox writes outside the target or into the caller's repo | — | — | resolved by removal: S15 deletes the sandbox (reviews 1–3 found same-user routes into the caller's repo); setup writes only in the repo it runs in |
| Removing the sandbox leaves dead code or stale doc mentions | medium | low | S15's static test checks the docs, the usage line and the template directory; `make check` (lint) flags unused imports |
| The setup skill nudges the agent to apply human-owned changes | low | high | the skill only runs `--dry-run`, and applies after the human confirms in chat; R-4 is enforced in code, not only in the skill |
| Running under `CLAUDECODE` in CI/evals changes behaviour | low | low | tests set and unset `CLAUDECODE` explicitly per case |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_setup.py::Plan::test_dry_run_writes_nothing`, `::Init::test_init_actions_preview_matches_apply` | cli | dry run prints the four sections and changes nothing |
| AC-2 | `tests/test_setup.py::Apply::test_fresh_repo_each_profile` | cli | solo/team/strict initialize with their config values; code read-only |
| AC-3 | `tests/test_setup.py::Apply::test_rerun_plans_nothing` | cli | idempotent rerun |
| AC-4 | `tests/test_setup.py::Owned::test_agent_never_writes_existing_owned_files` | cli | agent leaves existing config/settings untouched and prints human steps |
| AC-5 | `tests/test_setup.py::Owned::test_human_merges_only_marketplace_keys` | cli | only the marketplace keys are added; permissions/hooks unchanged; profile diff applied |
| AC-6 | `tests/test_setup.py::Plan::test_no_tty_needs_yes` | cli | no tty and no `--yes` → exit 2, no writes |
| AC-7 | `tests/test_engine.py::Approvals::test_strict_policy_requires_a_touch_key` | unit | the `"sk"` policy accepts only touch `sk-` keys |
| AC-8 | `tests/test_playbook.py::Playbook::test_solo`, `::test_team`, `::test_strict` | hook, cli | the playbook workflow holds in every profile |
| AC-9 | `tests/test_cli.py::Init::test_scaffold_offers_the_plugin` | cli | init writes the marketplace snippet, deny list intact |
| AC-10 | `tests/test_setup.py::NoSandbox::test_unknown_option_refused`, `::test_docs_offer_the_recipe_not_a_sandbox` | cli, static | unknown options (`--sandbox` included) are refused with nothing written; the README gives the recipe; no sandbox mention or template remains |
| AC-11 | `tests/test_setup.py::Preflight::test_rows_and_blocking` | cli | `!` rows with fixes; `✗` stops before writes; no token flags |
| AC-12 | `tests/test_shell_hooks.py::ShellHooks::test_onboarding_docs`, `::test_setup_skill_follows_the_playbook` | static | task-first README, docs, templates, quick ref matches skills |
| AC-13 | `tests/test_setup.py::Feedback::test_prints_links_offline` | cli | feedback prints links, no network |
| AC-14 | `tests/test_shell_hooks.py::ShellHooks::test_version_matches_changelog` | static | 0.2.0-alpha.2 everywhere |
| AC-15 | `tests/test_cli.py::Lifecycle::test_strict_requires_codeowners` | cli | strict fails without CODEOWNERS on `.aiops/`; others warn |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-03 | S7 | `lib/sdlc_engine/cli.py` changed too (S7 listed only `setup.py`). The `.gitignore` entry moved from `cmd_init` into `apply_init`, so init and setup share it. `codeowners_cover_aiops` (S4) no longer counts the scaffold's `@your-org/...` placeholders as owners; `test_strict_requires_codeowners` pins that | otherwise setup would skip the ignore line, and `strict` would pass on a fresh scaffold with no real owner | S7 commit |
| 2026-11-03 | S9 | The sandbox's Makefile uses its own stdlib-only recipes (`templates/sandbox/sandbox.recipes`: `py_compile`, `unittest`) instead of the python preset (ruff, mypy, pytest). `cli._wire_stack` gained an optional recipes-file argument for it. The sandbox also refuses a directory inside the calling repo | AC-10 needs `make check` green on any machine, and none of ruff, mypy or pytest is guaranteed; a sandbox inside the repo would touch it | S9 commit |
| 2026-11-03 | S12 | A pin, with no red from the engine (agreed in the stress test): the conformance walk passed once the test's own bugs were fixed (calling bin/sdlc without python3 on the stub PATH, and not ticking plan steps before state 5). Instead, a mutation check proved it bites: with the pre-edit read-only lock disabled, all three profiles fail at `('<profile>', 'intent')`. For team/strict the test plays the human's accepted key by patching only `approvals.key_protection` (and `_signing_key_files` for strict); the approval commits are still really signed | a passphrase prompt or an sk- touch can't run in a test | S12 commit |
| 2026-11-03 | S13 | "Pinned install commands" (R-7): the README states the current release and how to check it (`/plugin list`) instead of a version-pinned `/plugin` command or a `ref` in the settings snippet, because I couldn't verify that either syntax exists. Consumer CI is already pinned to the release tag by `init`/`setup` (`ZOUJ_SDLC_REF`). Also fixed: the README's stale "58 tests" line, and `.github/ISSUE_TEMPLATE/config.yml` gains a troubleshooting link | don't document syntax that may not work | S13 commit |
| 2026-11-03 | — | **Human decision:** review round 1 returned CHANGES_REQUESTED (76/100). Fix the HIGH, MAJOR and MEDIUM findings in state 5 as review-fix commits (F1–F6), each test first; the MINOR/LOW findings become 0.2.0-alpha.3 known issues; then review again | "Fix HIGH+MAJOR+MEDIUM" | — |
| 2026-11-03 | F1 | The sandbox is built in a private `mkdtemp` directory next to the target and moved into place with one `os.rename` (never follows a symlink); git's toplevel is checked and an explicit file list is committed; a failed build is removed. Also fixed the MINOR "inside this repo" refusal when the caller isn't in a git repo. Proof tests: `SandboxRace::test_target_swapped_for_a_symlink_mid_build`, `Sandbox::test_outside_any_repo` | review round 1 HIGH: the agent could swap the target for a symlink mid-build and commit a solo downgrade into the real repo | F1 commit |
| 2026-11-04 | F2 | `cli.init_actions` gains `agent`: under the agent, `--force` keeps existing human-owned scaffold files (`HUMAN_OWNED_RE`: `.aiops/config.json`, `.aiops/config/`, `.claude/`, CODEOWNERS, `.github/workflows/`) and `init` lists them for the human. Doctor's Makefile fix and TROUBLESHOOTING no longer suggest `init --force`. Proof test: `Init::test_agent_init_force_keeps_human_owned_files` | review round 1 HIGH: the agent's `init --force` silently turned strict into team and reset signers, settings, CODEOWNERS and workflows | F2 commit |
| 2026-11-04 | F3 | The unified diffs of human-owned changes are printed in the Plan section (dry run included), before the Gates and the `[y/N]`; `apply()` no longer prints them again. A `_is_tty()` helper lets the test simulate a terminal. Proof test: `Owned::test_diff_shown_before_confirmation` | review round 1 MAJOR: the human confirmed without seeing the diff (R-4, AC-5) | F3 commit |
| 2026-11-04 | F4 | Preflight gains `owned_json_rows`: an existing `.aiops/config.json` or `.claude/settings.json` that isn't valid JSON is a `✗` row with the parser error, so setup (and `--dry-run`) stops before writing and never says "Already set up". Proof test: `Owned::test_invalid_json_is_refused` | review round 1 MAJOR: setup skipped a corrupt file silently and reported success with the default profile | F4 commit |
| 2026-11-04 | F5 | Under `approval_key_policy: "sk"` (read from the base ref in CI), `approvals.audit` also requires the approval's signer (git `%GK`, matched by fingerprint to its allowed-signers entry) to be an `sk-` key without `no-touch-required`; doctor flags any other allowed-signers entry under strict. The accept path is covered by proving the fingerprint match (`%GK` == the entry's `ssh-keygen -l`), since a test can't make a real sk- signature. Proof test: `Approvals::test_audit_requires_a_touch_key_under_strict` | review round 1 MEDIUM: strict was enforced only when signing locally; CI accepted an ordinary-key approval | F5 commit |
| 2026-11-04 | F6 | The scaffold's marketplace source gains `"ref": "__ZOUJ_SDLC_REF__"` (filled with `v<version>` by `apply_init`, like CI's `ZOUJ_SDLC_REF`); `setup.MARKETPLACE` and the human steps pin `@v<version>`; README (install A, snippet C, a "What you trust" note) and SECURITY.md state the trust model. Verified first in the Claude Code docs: a `github` marketplace source accepts `ref`, and `marketplace add` accepts `owner/repo@ref`. This also resolves S13's "no pinned install commands" deviation. Setup now compares the snippet's values, not only its keys, so an older ref or a fork is `!` and proposed as a change (closing a round-1 LOW; that test was written with its fix). CHANGELOG lists the round-1 fixes and the alpha.3 known issues. Proof tests: `Init::test_scaffold_offers_the_plugin`, `Apply::test_fresh_repo_each_profile` (pins), `Owned::test_stale_or_foreign_marketplace_is_proposed` | review round 1 MEDIUM: the snippet enabled whatever the default branch held, and the docs didn't say what enabling the plugin trusts | F6 commit |
| 2026-11-04 | — | **Human decision:** review round 2 returned CHANGES_REQUESTED (80/100). F1 was incomplete (the build directory or its parent could still be swapped). Fix it properly (G1), fix the doctor regression from F5 (G2), correct the F1/CHANGELOG wording; the round-2 LOWs join the alpha.3 known issues; then review round 3 | "Fix it properly" | — |
| 2026-11-04 | G1 | The sandbox is built through handles: the parent is opened once with `O_NOFOLLOW`, the build directory is created and entered relative to it (`os.mkdir(dir_fd=)`, `os.fchdir`), every write and git call uses relative paths, git's toplevel is checked by inode, the build name is re-checked by inode before the rename, and the rename goes through the parent handle. A failed build is emptied and removed through its handle. F1's claim "the sandbox build can't be redirected" was wrong at F1 (it covered only the target). Proof tests: `SandboxRaceDeeper::test_build_dir_swapped_for_a_symlink`, `::test_parent_swapped_for_a_symlink`. `SandboxRace` now uses a private parent (it had scanned `/tmp`, where a leftover from an intermediate run of this fix sat; removed) | review round 2 BLOCKER/HIGH: a strict→solo downgrade committed into the calling repo, reproduced by two reviewers | G1 commit |
| 2026-11-04 | G2 | `cmd_doctor`: the CODEOWNERS `if strict … else` is self-contained again and the `"sk"` allowed-signers block follows it (F5 had put it between the `if` and its `else`). CHANGELOG: the sandbox entry now describes the handle-pinned build and says the first fix covered only the target; the round-2 LOWs are listed as alpha.3 known issues. Proof test: `Lifecycle::test_strict_requires_codeowners` (mixed profile/policy configs) | review round 2 MINOR (a regression from F5) and the inaccurate CHANGELOG claim | G2 commit |
| 2026-11-04 | — | **Human decision:** review round 3 returned CHANGES_REQUESTED (78/100); every remaining finding is in the sandbox. Remove the sandbox entirely: no deferral and no later phase. The README shows a throwaway-repo recipe instead, and setup refuses unknown options. Intent, spec and plan were amended (S15) and need re-approval. A first amendment that deferred it to alpha.3 (380ac27) was not approved | "Drop sandbox from alpha.2", then "i do not approuve, remove sandbox" | this amendment |
| 2026-11-04 | S15 | Done as planned. `_wire_stack` is back to its main signature (the recipes-file argument existed only for the sandbox), and `datetime` and `secrets` imports went with it. The onboarding test in `tests/test_shell_hooks.py` now expects the **Just looking?** recipe instead of `--sandbox`. The red run of `NoSandbox` built one real sandbox in `/tmp`, removed afterwards. About 670 older side directories from earlier test runs remain in `/tmp`: the agent's sweep was refused, so the human removes them; the suite-wide leak stays an alpha.3 known issue | the sandbox is gone, so code that only served it goes too | S15 commit |
| 2026-11-04 | — | **Human decision:** review round 4 returned CHANGES_REQUESTED (84/100). Fix the HIGH (scaffold writes follow symlinks: H1), the MEDIUM (the agent's new config gets its own profile: H2), and the minor/low items (setup: `--stack` whitelist, unknown stored profile, one argument parser: H3; docs: recipe path and commit step, `--force` claim, CHANGELOG headings/known issues/date, roadmap lines: H4), each test first; then review round 5 | "Fix HIGH+MEDIUM+minor" | — |
| 2026-11-04 | H1 | Scaffold and setup writes no longer follow links. `init_actions` marks a scaffold file (or `.gitignore`) with a symlink anywhere on its path as `symlink`; `init` refuses up front (exit 1, the links listed, nothing written), and setup's plan shows it as `✗` and stops. Every write goes through `cli.write_file`: directories opened relative to their parent with `O_NOFOLLOW`, the file removed and created anew with `O_EXCL`, so a link that appears after the preview raises instead, and a hard link is replaced, not written through. `_wire_stack` now takes the repo root so the Makefile goes through it too. Other engine writes (`new`, `draft`, state files) predate this intent and are unchanged. Proof tests: `Symlinks::*` (5) | review round 4 HIGH: `init --force` under the agent overwrote `.claude/settings.json` through a `REVIEW.md` symlink, and links led outside the repo | H1 commit |
| 2026-11-04 | H2 | Under the agent, a `config.json` that setup creates is exactly init's scaffold config (team defaults); the requested profile is printed as a human step ("Change .aiops/config.json yourself"), through the existing pending-changes path. The plan's note says so. A human run still writes the profile. `skills/setup/SKILL.md` step 5 says this. Proof test: `Owned::test_agent_creates_a_missing_config_with_init_defaults` (an initialized repo without config, and a fresh repo) | review round 4 MEDIUM (and the security LOW on fresh repos): the agent could create a solo config, contrary to R-4 | H2 commit |
| 2026-11-04 | H3 | Setup reads its arguments once (`setup.parse`): each option's value is checked against its allowed names (`cli.PROFILES`, `cli.STACKS`) before preflight, dry run included, so `--stack` is a preset name only, a value can't double as a flag, a missing value and `--profile=x` are refused with exit 1. `init --stack` takes only the preset names too. An unknown stored profile stops `setup --dry-run` with the fix instead of a `KeyError`, and doctor's profile row is `✗` for it. Proof tests: `Plan::test_arguments_parsed_once_and_checked_up_front`, `Plan::test_unknown_stored_profile` | review round 4 LOW/MINOR (security: `--stack` any path; code: two parsers, the `KeyError`) | H3 commit |
| 2026-11-04 | H4 | Docs match the code. README "Just looking?" uses `<plugin>/bin/sdlc setup --profile solo --yes` (or `/zouj-ai-sdlc:setup solo`) and commits the scaffold. The scaffold Makefile and `init`'s "Kept existing" line no longer suggest `--force`. CHANGELOG: the alpha.2 date is 2026-11-04 (the release manager adjusts it at tagging), the Security heading covers every review round and lists H1/H2, Changed lists H3, and the fixed argument-parsing known issues are gone; the `/tmp` test leak is listed. Roadmap Phase 1: the scope choice and init's confirmation are marked not shipped (setup has the confirmation). Proof tests: `ShellHooks::test_docs_match_what_shipped`, `Init::test_init_actions_preview_matches_apply` (no `--force` hint) | review round 4 MINOR/LOW docs findings | H4 commit |
| 2026-11-04 | — | **Human decision:** review round 5 returned CHANGES_REQUESTED (89/100, no HIGH). Fix everything, each test first: AC-8's FAIL-review case (J1); the docs promising a solo setup through the skill, the agent-run human step wording and the agent rerun (J2); setup/init refusing a root that isn't a git work tree or is `$HOME`, `~/.claude` or the plugin (J3); non-object JSON, write errors, preflight binary resolution (J4); case-insensitive `no-touch-required` (J5); the CHANGELOG `--force`/`--stack` wording, TROUBLESHOOTING's ✗ list and the env-marker residual risk (J6, stated in the skill and `docs/architecture.md`, not the approved spec). Then review round 6 | "Fix everything" | — |
| 2026-11-04 | J1 | `Playbook.walk` now commits a CHANGES_REQUESTED review, checks state 5, merges it into main, checks it is still state 5 (not DONE), undoes that merge, then continues with the PASS review. A pin like S12: the engine already behaved correctly, so there is no red run. Mutation check instead: with `machine.py:229` accepting any verdict on main, all three profile tests fail (`6 != 5`); the file was restored (no diff). Proof tests: `Playbook::test_solo`, `::test_team`, `::test_strict` | review round 5: AC-8 partial (no FAIL-review case) | J1 commit |
| 2026-11-04 | J2 | Run by the agent, setup's human step for the profile is now "Apply profile <p> in your own terminal", with the exact `<plugin>/bin/sdlc setup --profile <p>` command and the keys it sets. An agent rerun counts only `+` (new files) as its writes: with only `~` (human-owned) changes left it prints "Nothing for the agent to write", the human steps, and exits 0 without asking. README (recipe and path A), the quick reference and the setup skill (steps 1 and 5) say a non-team profile is applied by the human's own terminal run; the recipe no longer offers `/zouj-ai-sdlc:setup solo`. Two `Owned` assertions and H4's docs test were updated for the new wording; the skill's step 1 names the command without `--yes` (the skill test requires `--dry-run` before `--yes`). Proof tests: `Owned::test_agent_hands_the_profile_to_the_human_and_reruns_cleanly`, `ShellHooks::test_docs_match_what_shipped` | review round 5 MEDIUM (docs promised a solo setup through the skill), MINOR (human-step wording), LOW (agent rerun) | J2 commit |
| 2026-11-04 | J3 | `cli.scaffold_root_problem`: init and setup (dry run included) refuse, before anything else and with nothing written, a root that isn't the top of a git work tree (closing `project_root`'s fallback to the current directory), the home directory, anything under `~/.claude`, or a toolchain path (the guard's own `_toolchain_path`: PATH directories, shell startup, installed plugins). Only the root is checked: the toolchain globs match every repo's `.claude/settings.json`. The plugin's own directory is not refused by itself (this repo is the plugin and dogfoods its workflow; installed copies sit under `~/.claude`). A first draft of the test's cleanup computed a parent that resolved to `/tmp` itself; the permission check refused that command before it ran, and the test now removes only the directory it created. Proof tests: `Roots::*` (4) | review round 5 security MEDIUM: `cd ~ && sdlc setup` under the agent created `~/.claude/settings.json` and `~/.claude/CLAUDE.md` | J3 commit |
| 2026-11-04 | J4 | (a) JSON of the wrong shape: setup's `owned_json_rows` gives `✗` for a human-owned file that isn't an object or whose marketplace key isn't an object, `_json` returns only objects, and `machine.config` reads a non-object `config.json` as the defaults (as it already did for invalid JSON; this touches the engine, outside setup). (b) Write errors: `apply_init` records each file it writes; `init` and `setup` catch `OSError` and print `cli.write_failure` (what failed, the files written before it), exit 1. Setup's "Applied" lines now print after all writes succeed. (c) Preflight drops PATH directories inside the repo (`_outside_repo`), runs git's credential check with the engine's absolute git, and closes stdin for every tool it runs. Proof tests: `Owned::test_json_that_isnt_an_object_is_refused`, `WriteErrors::*` (2), `PreflightTools::test_planted_tools_are_not_run` | review round 5 LOW (non-object JSON, write errors, preflight binaries) | J4 commit |
