---
id: 0012
title: Opt-in dsl part: a validated domain/ model for specs and plans
status: Approved
spec: ./spec.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T16:31:26Z
approved-via: cli
approved-sha256: 815e878b720f948db53407afbc8d69d889c67d4e94ae52f6b77fcafa0c0eb648
---

# Plan: Opt-in dsl part: a validated domain/ model for specs and plans

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Five TDD steps and one verification step, ordered so that each step's proof test can fail on its own:

1. **S1 registers the part** with its README only. `parse_parts("dsl")` is unknown today, so the tests start red.
2. **S2 adds the validator**, which then joins the part.
3. **S3 changes the Makefile template.**
4. **S4 adds the spec check and the draft section.**
5. **S5 adds the written guidance.**
6. **S6 verifies.**

Code reused:
- **Parts:** `lifecycle.PARTS`, `parse_parts`, `parts_line` and `installed_parts` (`lib/sdlc_engine/lifecycle.py:104-215`).
  The "every part" fallbacks are at `:209`, `:213` and `:268`, and setup reads the parts at `setup.py:337`, `:483`.
- **Makefile:** wiring replaces only `not configured` stub lines (`cli.py:426-441`), so a `validate-dsl` recipe that
  isn't a stub is never rewired. `stub_makefile` compares with the current template (`cli.py:493`).
- **Human steps:** `setup.human_steps` (`setup.py:640`) is where the Makefile step goes.
- **Spec checks:** 0011's check signature `(d, a, secs, text)` and the tuple-or-list protocol (`schema.py:36-42`).
- **Spec draft:** `cli.cmd_draft` (`cli.py:231`).
- **Scaffold history:** `scripts/scaffold-history.py` regenerates the `unreleased` entry. The 0009 relaxation in
  `Docs::test_changelog_has_the_release` allows it while `[Unreleased]` has entries, which it does (0011).

## Steps
- [x] **S1**: Register the `dsl` part: explicit opt-in, never through `all` or the legacy fallbacks.
  - **Files:**
    - `tests/test_lifecycle.py` (modify):
      - `Parts::test_parse_parts`: `all` → the five legacy parts, `all,dsl` → six, `dsl` alone → `["dsl"]`;
      - a new `DslPart` class:
        - `test_legacy_state_without_parts_has_no_dsl`: install-state with no `parts` key gives `LEGACY_PARTS`;
        - `test_edited_config_without_state_has_no_dsl`;
        - `test_upgrade_and_repair_plan_no_dsl_file`: an old-style state, `upgrade --dry-run` and
          `repair --dry-run` list no `domain/` path (AC-1).
    - `tests/test_setup.py` (modify): `Apply::test_with_dsl_installs_the_part` and
      `::test_with_all_leaves_dsl_out`:
      - run as the human (no agent markers), `setup --with dsl --yes` records `dsl` in install-state `parts`, writes
        `domain/README.md`, and changes no existing file;
      - `--with all` writes no `domain/` file (AC-1).
    - `lib/sdlc_engine/lifecycle.py` (modify):
      - `PARTS` gains `dsl`, and `LEGACY_PARTS` holds the other five;
      - `parse_parts` accepts `all` beside names, and `all` means `LEGACY_PARTS`;
      - `installed_parts` and the `:268` fallback use `LEGACY_PARTS`;
      - `parts_line` says `all` excludes `dsl`.
    - `lib/sdlc_engine/cli.py` (modify): the usage text lists `dsl` and says `all` leaves it out.
    - `lib/sdlc_engine/setup.py` (modify): the `--with` help line at `:428`.
    - `defaults/scaffold-parts` (modify): the comment, and the line `dsl domain/*`.
    - `templates/scaffold/domain/README.md` (create): the R-3 format, one example per kind, how to validate
      (`make validate-dsl`), and the spec's `## Domain DSL` rule.
    - `defaults/scaffold-history.json` (regenerate).
  - **Test first:** `parse_parts("dsl")` returns "unknown part", and setup has no `dsl` to install.
  - Covers: AC-1
- [x] **S2**: Ship the stdlib validator `scripts/validate-dsl.py` in the part.
  - **Files:**
    - `tests/test_dsl.py` (create): runs the script with `sys.executable` on temp directories:
      - valid models of all three kinds → exit 0 and `validate-dsl: 3 model(s) ok`;
      - one test per problem class, each asserting the exit code 1 and the exact `<file>: <json path>: <problem>`
        line (or `<file>:<line>:<col>: invalid JSON`):
        - invalid JSON;
        - wrong `dsl` version;
        - unknown kind;
        - unknown key;
        - an unknown state in `from`/`to`;
        - a duplicate (`from`, `event`) pair;
        - a missing or unknown `initial`;
        - a `final` that isn't a state;
        - a duplicate rule id;
        - an empty `when`;
        - an unknown `next` step;
        - an unknown `start`;
        - a duplicate `name` across files;
      - no directory → exit 0 with the skip line;
      - safety: a symlinked `*.dsl.json` is a problem and not followed, a file over 1 MiB and nesting over 64
        levels are problems (never a traceback), and `README.md` and other files are ignored (AC-2).
    - `templates/scaffold/scripts/validate-dsl.py` (create): the validator, stdlib only (Python 3.9). Files are
      opened with `O_NOFOLLOW`, the size is checked before reading, and the depth is checked iteratively on the
      parsed value; `RecursionError` from `json` is caught as well.
    - `defaults/scaffold-parts` (modify): `dsl scripts/validate-dsl.py`.
    - `tests/test_setup.py` (modify): `test_with_dsl_installs_the_part` also expects the script.
    - `Makefile` (modify): `lint` and `typecheck` also cover `templates/scaffold/scripts/` (with ruff, if
      installed, and `compileall`).
    - `defaults/scaffold-history.json` (regenerate).
  - **Test first:** `tests/test_dsl.py` fails: the script doesn't exist.
  - Covers: AC-1, AC-2
- [x] **S3**: Run `validate-dsl` from `make check` in the core Makefile template.
  - **Files:**
    - `tests/test_dsl.py` (modify): a `MakeCheck` class, skipped without `make`. In a temp dir with the rendered
      template Makefile:
      - `make check`: no `domain/` → exit 0 with the skip line; a valid `domain/` plus the script → 0; an invalid
        one → non-zero; `domain/` without the script → non-zero, naming `sdlc setup --with dsl` (AC-3).
    - `tests/test_lifecycle.py` (modify): `Detected::test_wired_makefile_keeps_recipes_with_validate_dsl`: a
      Makefile wired by detection, after `upgrade`, keeps its recipes and gains the target (AC-3).
    - `tests/test_setup.py` (modify): `test_with_dsl_on_an_edited_makefile_prints_the_step`: an edited Makefile
      without `validate-dsl` isn't changed, and the human steps show the target and the `check` line.
    - `templates/scaffold/Makefile` (modify): the `validate-dsl` target (in `.PHONY`, with a `##` help) and
      `check: lint typecheck test validate-dsl`. Its recipe is a POSIX `if [ -d domain ]` that runs
      `python3 scripts/validate-dsl.py`, or fails naming `sdlc setup --with dsl` when the script is missing.
    - `lib/sdlc_engine/setup.py` (modify): `human_steps` adds the Makefile step while `dsl` is installed and the
      Makefile defines no `validate-dsl:`.
    - `defaults/scaffold-history.json` (regenerate).
  - **Test first:** `make check` with an invalid `domain/` passes today, because the template has no such target.
  - Covers: AC-3
- [x] **S4**: Require `## Domain DSL` in spec.md while the part is active, and put it in the spec draft.
  - **Files:**
    - `tests/test_engine.py` (modify): a `DomainDsl(RepoCase)` class:
      - `test_inactive_needs_no_section`;
      - `test_active_by_install_state` and `test_active_by_domain_dir`: a spec with no section errors;
      - `test_accepted_bodies`: `No domain changes`, `No domain changes: CSS only`, and a body naming
        `domain/order.dsl.json` pass;
      - `test_rejected_bodies`: an empty body, a comment only, and an unrelated body error, with a message naming
        both accepted forms;
      - `test_legacy_state_is_not_active`: no `parts` key, so not active even though `installed_parts` says every
        legacy part;
      - `test_approved_spec_keeps_its_gate`: activating the part doesn't change `gate()` (AC-4).
    - `tests/test_cli.py` (modify): `test_draft_spec_adds_domain_dsl_when_active`: the section comes before
      `## Data model` while active and is absent while inactive (AC-4).
    - `lib/sdlc_engine/lifecycle.py` (modify): `dsl_active(root)`.
    - `lib/sdlc_engine/schema.py` (modify): `_domain_dsl` and `"domain_dsl"` in `CHECKS`.
    - `schemas/spec.json` (modify): `checks` gains `domain_dsl`.
    - `lib/sdlc_engine/cli.py` (modify): `cmd_draft` inserts the section fragment before `## Data model` when
      `dsl_active`.
  - **Test first:** the active-part tests find no error, and the draft has no section.
  - Covers: AC-4
- [x] **S5**: Write the written guidance into the skills, agents and docs.
  - **Files:**
    - `tests/test_cli.py` (modify): `Docs::test_dsl_guidance` checks for key phrases:
      - `skills/spec/SKILL.md` and `agents/architect.md`: `## Domain DSL` before Data model and API contracts,
        while the part is active;
      - `skills/plan/SKILL.md` and `agents/planner.md`: S1 is `domain/` and `make validate-dsl`;
      - `skills/setup/SKILL.md` and `skills/init/SKILL.md`: `dsl`, and that `all` excludes it;
      - `docs/state-machine.md`: the `domain_dsl` row;
      - `docs/architecture.md`: install-state "only adds" a requirement;
      - the CHANGELOG `[Unreleased]`: `.aiops/0012-dsl-part/` (AC-5).
    - Those files (modify), plus the part lists in `README.md`, `docs/install.md`, `docs/adoption.md`,
      `docs/roadmap.md`, `TROUBLESHOOTING.md` and `templates/scaffold/.aiops/README.md` wherever they list the
      parts.
  - **Test first:** `Docs::test_dsl_guidance` fails on the missing phrases.
  - Covers: AC-5
- [ ] **S6**: Prove the change.
  - **Commands:**
    - `make check`;
    - `make validate`;
    - `bin/sdlc validate --all`;
    - `python3 scripts/scaffold-history.py --check`;
    - `git diff --name-only main...HEAD`: only the files S1-S5 name and `.aiops/0012-*`;
    - a manual run in a scratch repo: `sdlc setup --with dsl --yes`, an invalid `domain/order.dsl.json`, then a
      valid one, and `make check` each time.
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-3, AC-5

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Adopters' `make check`, which runs in every Stop hook, breaks after `upgrade` | low | high | The target is dormant without `domain/` (S3 test). Only `--with dsl` creates `domain/`. A wired Makefile keeps its recipes (S3) |
| The template change makes an older untouched Makefile stop counting as the stub (`stub_makefile` compares with the current template) | medium | low | `upgrade` already replaces an untouched older template (history hashes), after which it is the stub again; S3's `upgrade` test covers it |
| `dsl` leaks into old repos through the "every part" fallbacks | medium without S1 | high: specs suddenly need a section | `LEGACY_PARTS` in every fallback, and S1's three legacy tests |
| A crafted model file crashes or slows the validator in the Stop hook | low | medium | `O_NOFOLLOW`, a 1 MiB limit, the depth limit, and `RecursionError` caught (S2 safety tests) |
| Anaconda's `ruff` 0.15.1 on PATH reformats the repo if the hooks load | high if the hooks load | high | `git status` after each edit, restore anything outside the step, or restart with ruff off PATH |
| CI lint (shellcheck, ruff 0.6.9) stricter than local | medium | low | The new script goes under lint in S2, plus a manual check for unused names; watch `gh pr checks` |
| `domain/` deletion lifts the CI requirement (spec flag, accepted) | low | medium | Visible in the PR diff; decided in the spec |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_setup.py::Apply::test_with_dsl_installs_the_part`, `::test_with_all_leaves_dsl_out`; `tests/test_lifecycle.py::Parts::test_parse_parts`, `::DslPart::test_legacy_state_without_parts_has_no_dsl`, `::test_edited_config_without_state_has_no_dsl`, `::test_upgrade_and_repair_plan_no_dsl_file` | integration, unit | explicit opt-in only, recorded, only missing files written |
| AC-2 | `tests/test_dsl.py` (valid models, one test per problem class, the skip, the safety tests) | CLI | exit codes and the located problem lines |
| AC-3 | `tests/test_dsl.py::MakeCheck`, `tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl`, `tests/test_setup.py::…::test_with_dsl_on_an_edited_makefile_prints_the_step`; S6 manual run | integration | `make check` dormant without `domain/`, fails on an invalid model, recipes kept |
| AC-4 | `tests/test_engine.py::DomainDsl` (7 tests), `tests/test_cli.py::…::test_draft_spec_adds_domain_dsl_when_active` | unit, CLI | the conditional section, both accepted forms, activation rules, gates untouched |
| AC-5 | `tests/test_cli.py::Docs::test_dsl_guidance`; S6 `make check` | doc | the advice ships |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-20 | S1 | Seven existing tests not named in S1 changed to the new meaning of "every part" (`LEGACY_PARTS`): `test_setup.py::Init::test_init_actions_preview_matches_apply`, `::Parts::test_with_maintain_adds_only_maintain`; `test_cli.py::InitParts::test_with_all`, `::test_edited_config_without_state_gets_every_part`, `::test_template_config_with_full_scaffold_gets_every_part`; `test_lifecycle.py::Compat::test_release_repo_without_state_keeps_every_part`, `::InstallState::test_init_records_every_file` (now `--with all,dsl`) | They asserted that `--with all` and the legacy fallbacks cover every scaffold file, which R-1/R-2 make untrue for `dsl` by design | S1 green commit |
| 2026-11-20 | S1 | `parts_line` lists only missing legacy parts and names `dsl` as installed by name, rather than listing `dsl` as missing | Otherwise every repo set up with `--with all` would be told `dsl` is "not installed" forever; `dsl` is a choice of method, not a gap. `CoreOnly::test_list_installed_hides_parts_not_installed` keeps passing unchanged | S1 green commit |
| 2026-11-20 | S2 | `typecheck` compiles the scaffold scripts with `compile()` instead of `compileall` | `compileall` would write `__pycache__/` into `templates/scaffold/scripts/`, and every file there counts as a scaffold file | S2 green commit |
| 2026-11-20 | S2 | `templates/scaffold/scripts/check-bands.py` (maintain part, not named in S2): `l` renamed to `line` (ruff E741); `Parts::test_core_is_sixteen_files` counts 22 opt-in files | The first ruff run over the scaffold scripts; fixing its findings in S2 was agreed at the plan review. The count follows the new script | S2 green commit |
| 2026-11-20 | S3 | The red test `Detected::test_wired_makefile_keeps_recipes_with_validate_dsl` was corrected in the green commit: the older Makefile is recorded as written by `0.2.0-beta.1`, not `0.2.0-beta.2` | `0.2.0-beta.2` is the running plugin's own version, so the file read as `current` and the test could never see `stale`. The rebuilt older template was checked byte-equal to `main`'s | S3 green commit |
| 2026-11-20 | S4 | `domain_dsl` applies only while the spec's gate is closed: an approved, unchanged spec is exempt (spec R-6 required the section of every spec while the part is active). `test_approved_spec_keeps_its_gate` asserts the exemption, and that an edit after approval brings the requirement back | As written, R-6 would turn `sdlc validate --all --ci` red for every earlier approved spec of a repo that adds `dsl` after it has history. This follows 0011's `scope_size` precedent. **Needs the human's confirmation at review** | S4 green commit |
| 2026-11-20 | S4 | The gate test shared by `scope_size` and `domain_dsl` is extracted as `schema._gate_open` | Two checks now need it (0011 review backlog item 3) | S4 green commit |
| 2026-11-20 | S5 | `docs/install.md`, `docs/adoption.md` and `TROUBLESHOOTING.md` are unchanged (they don't list the parts), and so is `docs/roadmap.md:72`, a record of what 0.2.0-beta.1 shipped. `docs/architecture.md` gains a threat-model row for removing `domain/` | The plan named them "wherever they list the parts"; none does except the roadmap's history. The new row records the spec's accepted flag | S5 green commit |
