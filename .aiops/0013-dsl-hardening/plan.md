---
id: 0013
title: Harden the dsl part: safe detection, validator edge cases, implement and review guidance
status: Approved
spec: ./spec.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T18:10:29Z
approved-via: cli
approved-sha256: 532c3c408a0c4be9599e81893722c34cc3f16180f15aff4018d8f34ef6401497
---

# Plan: Harden the dsl part: safe detection, validator edge cases, implement and review guidance

<!-- State 3 PLAN, produced read-only: no source or test file was edited to write it.
     Steps are chronological and file-by-file. Each step is one TDD cycle: proof test first (red), then code (green).
     Ticking boxes and appending to the Deviation log keep the approval valid; any other change needs re-approval. -->

## Approach
Five TDD steps and a verification step. As in 0012, each code step gets a commit holding only its red tests, then
the code that turns them green.

1. **S1, the engine's detection** (the MEDIUM finding). The 0012 tests that turn the part on with a bare `domain/`
   move to a model file in the same red commit, so that the new bare-directory tests fail for the right reason.
2. **S2, the Makefile recipe.**
3. **S3, the validator's type checks and the symlinked directory.**
4. **S4, linear lookups**, proven by a timing test that the current O(n²) code fails.
5. **S5, the guidance and docs.**
6. **S6, verification.**

Code reused:
- `lifecycle.dsl_active` (`lib/sdlc_engine/lifecycle.py:111-119`); its two callers, `schema._domain_dsl`
  (`schema.py:~105-125`) and `cli.cmd_draft` (the `DOMAIN_DSL_SECTION` insertion, `cli.py:~199-250`).
- The `validate-dsl` recipe (`templates/scaffold/Makefile:33-36`) and `setup.makefile_dsl_step`, which copies the
  template's block, so the human step follows S2 automatically.
- The validator's lookups: `validate-dsl.py` `state_machine`, `workflow`, `unique_ids`, `main` (`names`), and the
  `kind` lookup in `check_model`.
- The `MakeCheck` and `ValidateDsl` tests (`tests/test_dsl.py`), `DomainDsl` (`tests/test_engine.py:~756-819`) and
  the draft test (`tests/test_cli.py:~250`).

## Steps
- [x] **S1**: Activate the part by model files or install-state, never by a bare `domain/`.
  - **Files:**
    - `tests/test_engine.py` (modify): in `DomainDsl`:
      - a helper `model()` writes `domain/x.dsl.json`;
      - `test_active_by_domain_dir` becomes `test_active_by_model_file`;
      - new `test_bare_domain_dir_is_not_active`: an empty `domain/`, and `domain/user.py`, need no section;
      - the accepted, rejected and approved tests use `model()` instead of `mkdir` (AC-1).
    - `tests/test_cli.py` (modify): `test_draft_spec_adds_domain_dsl_when_active`: a bare `domain/` (with
      `domain/user.py`) gives no section; a `domain/x.dsl.json` gives it (AC-1).
    - `lib/sdlc_engine/lifecycle.py` (modify): `dsl_active` checks install-state `parts` first, then whether
      `domain/` holds a `*.dsl.json` entry (`OSError` → False). Docstring updated.
    - `lib/sdlc_engine/schema.py` (modify): the `_domain_dsl` messages say "a domain/*.dsl.json file exists".
    - `lib/sdlc_engine/cli.py` (modify): the `DOMAIN_DSL_SECTION` comment says the same.
  - **Test first:** `test_bare_domain_dir_is_not_active` and the bare-directory draft case fail: the part is
    active today.
  - Covers: AC-1
- [x] **S2**: Run `validate-dsl` in the Makefile when the script or a model file exists.
  - **Files:**
    - `tests/test_dsl.py` (modify): in `MakeCheck`:
      - `test_no_domain_passes` expects `[validate-dsl] no dsl part - skipped`;
      - new `test_non_dsl_domain_dir_is_skipped` (`domain/user.py`, no script → pass, the skip line);
      - `test_domain_without_script_fails_and_says_how` writes a model file and expects the new message;
      - new `test_script_without_domain_passes` (the validator's own skip line) (AC-2).
    - `templates/scaffold/Makefile` (modify): the recipe from spec Architecture (`$$f`, `$$found` for make).
    - `defaults/scaffold-history.json` (regenerate).
  - **Test first:** `test_non_dsl_domain_dir_is_skipped` fails, because the current recipe fails on any `domain/`.
    The skip-line assertion also fails.
  - Covers: AC-2
- [x] **S3**: Report non-string references and a symlinked `domain/` in the validator, never raise.
  - **Files:**
    - `tests/test_dsl.py` (modify): in `ValidateDsl`:
      - `test_non_string_references`: one subtest each for `kind`, transition `from`, `to`, `initial`, a `final`
        entry, `start` and a `next` entry set to a list or an object; each expects exit 1, the problem at its
        path, and no `Traceback` in stderr;
      - `test_symlinked_domain_dir`: `domain` → a real directory with a valid model; expects exit 1 and
        `domain: a link, not followed (validate the real directory)`;
      - `test_file_named_domain_is_skipped` (AC-3).
    - `templates/scaffold/scripts/validate-dsl.py` (modify): string guards before every lookup (spec R-3), and the
      link check in `main` (R-4).
    - `templates/scaffold/domain/README.md` (modify): "Limits" says a linked `domain/` is reported.
    - `defaults/scaffold-history.json` (regenerate).
  - **Test first:** the `kind` and `from` subtests fail with a `TypeError` traceback (the two cases the 0012 review
    reproduced). The symlink test fails with exit 0 "skipped".
  - Covers: AC-3
- [x] **S4**: Make the validator's lookups linear with sets.
  - **Files:**
    - `tests/test_dsl.py` (modify): `test_large_model_is_linear`: a `state_machine` with 80,000 states and a few
      transitions, under 1 MiB. It must finish, exit 0, within 10 s (`time.monotonic`).
    - `templates/scaffold/scripts/validate-dsl.py` (modify): a set beside each list (states, step ids, rule ids,
      transition pairs, names). The order of reported problems is unchanged.
    - `defaults/scaffold-history.json` (regenerate).
  - **Test first:** the timing test fails today. The 0012 review measured 1.2 s for 20,000 states, which projects
    to about 19 s for 80,000.
  - Covers: AC-3
- [x] **S5**: Write the implement and review guidance and correct the activation wording in the docs.
  - **Files:**
    - `tests/test_cli.py` (modify): `Docs::test_dsl_hardening_guidance` checks:
      - `skills/implement/SKILL.md` and `agents/implementer.md`: "dsl part is active", `make validate-dsl`, and
        "before application code";
      - `skills/review/SKILL.md` and `agents/code-reviewer.md`: "hardcoded", "controllers", "UI", "MEDIUM",
        "3 points" and `## Domain model`;
      - that no shipped text still says the part is active when "`domain/` exists": a scan of the files R-8 names
        for the old phrases (AC-4, AC-5).
    - Text (modify):
      - `skills/implement/SKILL.md`, `agents/implementer.md` (R-6);
      - `skills/review/SKILL.md`, `agents/code-reviewer.md` (R-7);
      - for R-8: `skills/spec/SKILL.md`, `skills/plan/SKILL.md`, `agents/architect.md`, `agents/planner.md`,
        `templates/scaffold/domain/README.md`, `README.md`, `templates/scaffold/.aiops/README.md`,
        `docs/state-machine.md`, `docs/architecture.md` (the `domain/` removal row is now about the model files),
        and the unreleased 0012 entry in `CHANGELOG.md`, plus a line naming `.aiops/0013-dsl-hardening/`.
    - `defaults/scaffold-history.json` (regenerate, for the two scaffold READMEs).
  - **Test first:** `test_dsl_hardening_guidance` fails on the missing phrases and on the old wording.
  - Covers: AC-4, AC-5
- [ ] **S6**: Prove the change.
  - **Commands:**
    - `make check`;
    - `make validate`;
    - `bin/sdlc validate --all`;
    - `python3 scripts/scaffold-history.py --check`;
    - `git diff --name-only main...HEAD`: only the files S1-S5 name and `.aiops/0013-*`.
  - **Files:** none. The results go in the Deviation log and in review.md.
  - **Test first:** none; this step is the verification.
  - Covers: AC-2, AC-5

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The timing test is flaky on a slow CI runner | low | low: a red PR | A 10 s bound for work the set version does in well under a second; red today at about 19 s. If CI flakes, raise the bound and log it |
| The glob in the Makefile `for` loop expands to the literal pattern when nothing matches | certain (by sh semantics) | handled | `[ -e "$$f" ]` before setting `found`; `test_non_dsl_domain_dir_is_skipped` and `test_no_domain_passes` cover both empty cases |
| A 0012 test still turns the part on with a bare `domain/` and silently changes meaning | medium | medium | S1's red commit moves every `mkdir("domain")` activation in `test_engine.py` and `test_cli.py` to a model file; `test_dsl.py`'s are validator inputs, not activation |
| Narrower detection lifts a requirement a repo relied on | low | low | Only a repo with `domain/` but no model and no install-state entry is affected, which is the false positive being fixed; `--with dsl` still records `dsl` |
| Anaconda's `ruff` 0.15.1 on PATH reformats the repo if the hooks load | high if the hooks load | high | `git status` after each edit; restore anything outside the step |
| CI lint stricter than local | medium | low | Lint covers the scaffold scripts since 0012; watch `gh pr checks` |

## Test definitions
| AC | Test (file::name) | Type | Proves |
|---|---|---|---|
| AC-1 | `tests/test_engine.py::DomainDsl::test_bare_domain_dir_is_not_active`, `::test_active_by_model_file`, `::test_active_by_install_state`; `tests/test_cli.py::…::test_draft_spec_adds_domain_dsl_when_active` | unit, CLI | a non-DSL `domain/` activates nothing; a model file or install-state does |
| AC-2 | `tests/test_dsl.py::MakeCheck` (`test_no_domain_passes`, `test_non_dsl_domain_dir_is_skipped`, `test_script_without_domain_passes`, `test_valid_domain_passes`, `test_invalid_domain_fails`, `test_domain_without_script_fails_and_says_how`); `tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl` | integration | the recipe's three branches; wiring through upgrade |
| AC-3 | `tests/test_dsl.py::ValidateDsl::test_non_string_references`, `::test_symlinked_domain_dir`, `::test_file_named_domain_is_skipped`, `::test_large_model_is_linear` | CLI | no traceback, a reported link, linear time |
| AC-4 | `tests/test_cli.py::Docs::test_dsl_hardening_guidance` (implement parts) | doc | model first in State 4 |
| AC-5 | `tests/test_cli.py::Docs::test_dsl_hardening_guidance` (review parts and the wording scan); S6 `make check` | doc | the hardcoding check, MEDIUM with 3 points, the corrected docs |

## Deviation log
| Date | Step | Deviation from plan | Reason | Commit |
|---|---|---|---|---|
| 2026-11-20 | S5 | `README.md` and `templates/scaffold/.aiops/README.md` are unchanged, though S5 names them | Neither describes activation by `domain/`; both are still in the old-wording scan of `Docs::test_dsl_hardening_guidance`, so a later regression is caught | S5 green commit |
