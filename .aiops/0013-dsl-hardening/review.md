---
id: 0013
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 5ee366a847fa3e87ad17585fd79cf02b503a78b6
score: 95/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-20
---

# Review: Harden the dsl part: safe detection, validator edge cases, implement and review guidance

<!-- State 5 PRE-REVIEW. Written from the report of one fresh-context reviewer covering the three personas, who got
     only the intent folder and the base branch `main` (f8a4275), plus 0012's review for background. -->

## Summary
This fixes what the 0012 review found before release:
- The `dsl` part is active only through install-state or a `domain/*.dsl.json` file; a bare `domain/` never
  activates it.
- The Makefile runs the validator when the part's script or a model file exists.
- The validator reports a non-string reference or a linked `domain/` instead of raising or skipping, and it is
  linear: 24.7 s → 0.14 s on 80,000 states.

It also adds the implement guidance (model first) and the review's hardcoding check (MEDIUM, 3 points). No guard, gate
or audit path changes. **PASS, 95/100**: every AC is met, and there is no BLOCKER, CRITICAL, HIGH or MEDIUM finding.

The reviewer ran, without writing anything:
- **Targeted tests:** `test_dsl` 24 (and 7 subtests), `test_engine` DomainDsl/ScopeSizing 17, `test_cli`
  dsl/draft/Docs 16, `test_lifecycle` Detected/DslPart 9, all passing.
- **Validation:** `bin/sdlc validate --all` gave 0 errors across 12 intents, and `scaffold-history.py --check` is
  up to date.
- **In-memory probes:**
  - the S3 red cases raise `TypeError` on the pre-S3 validator;
  - 200,000 random mixed-type models through `check_model` raised no exception;
  - the recipe's loop doesn't abort under `dash -e` or `bash -e`.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `lib/sdlc_engine/lifecycle.py:111-123` (install-state first, then any `*.dsl.json`, `OSError` → False); `tests/test_engine.py::DomainDsl::test_bare_domain_dir_is_not_active` (`:795`), `::test_active_by_model_file` (`:791`), `::test_active_by_install_state` (`:784`), `::test_approved_spec_keeps_its_gate` (`:824`); `tests/test_cli.py::Lifecycle::test_draft_spec_adds_domain_dsl_when_active` (`:250`) |
| AC-2 | ✅ met | `templates/scaffold/Makefile:33-37`; `tests/test_dsl.py::MakeCheck` (`:268-302`: no domain, non-DSL `domain/`, script without domain, valid, invalid, model without script with the exact message); `tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl` (`:440`) |
| AC-3 | ✅ met | `tests/test_dsl.py::ValidateDsl::test_non_string_references` (`:179`, 7 subtests, no `Traceback`), `::test_symlinked_domain_dir` (`:201`), `::test_file_named_domain_is_skipped` (`:211`), `::test_large_model_is_linear` (`:218`: red 24.7 s, green 0.14 s); `templates/scaffold/scripts/validate-dsl.py:153-186`, `:213-223`, `:237-239`, `:254-260` |
| AC-4 | ✅ met | `skills/implement/SKILL.md:17`, `agents/implementer.md:25`; `tests/test_cli.py::Docs::test_dsl_hardening_guidance` (`:1036`) |
| AC-5 | ✅ met | `skills/review/SKILL.md:14,17`, `agents/code-reviewer.md:18` (controllers, handlers and UI; MEDIUM; 3 points; `## Domain model`; display literals and fixtures excluded; verdict rule unchanged); the activation wording is fixed in every shipped text; the same test scans for the old phrases, and a grep of shipped text found none left; `make check` green (S6) |

## Security
None found.
- **The Stop-hook validator:**
  - no crash path is left (the fuzzing found none), and the cost is no longer quadratic;
  - links are never followed, and special files are still opened `O_NONBLOCK` and checked by `fstat`;
  - the number of model files is unbounded, as the spec accepts.
- **The narrower detection** can be lifted only by deleting or renaming the model files (`.dsl.JSON`,
  `.dsl.json.bak`), or by replacing `domain/` with a regular file. All of these are the accepted "remove the model
  files" flag, visible as a PR diff; install-state keeps the requirement on locally. A symlinked `domain/` is
  followed by `dsl_active`, which can only add the requirement.
- **Guards and audit:** no file under `hooks/`, `guards.py`, `approvals.py`, `machine.py` or `schemas/` changed.

## Plan conformance
- S1-S6 match the plan file by file, with no change outside it.
- The one deviation is accurate: the two READMEs needed no change, and both stay in the old-wording scan.
- The scaffold-history hashes changed in place, which is correct because 0012 is unreleased; `--check` passes.

## Test-first evidence
Each step has a commit holding only its red tests, followed by its code commit:

| Step | Red | Green |
|---|---|---|
| S1 | 5341735 | cd65e42 |
| S2 | ec58d23 | ac4bf39 |
| S3 | 84a928e | 2cc3242 |
| S4 | 4a1af29 (red at 24.7 s) | b349a48 |
| S5 | 3049daa | ae8dcae |

The reviewer reproduced S3's red cases against the pre-S3 validator.

## Domain model
Not applicable. This repo has no `domain/*.dsl.json` model, so the dsl part isn't active here.

## Backlog (not blocking)
1. **A missing `kind`** now reads `$.kind: expected text (...)`, where it used to read `unknown kind "None"`.
   `$.kind: missing` would match how other keys report a missing value (`validate-dsl.py:237-239`).
2. **The engine, Makefile and validator disagree at the edges:**
   - a dotfile `domain/.x.dsl.json` activates the engine and is read by the validator, but the Makefile glob skips
     it;
   - a dangling-link model activates the engine, but the Makefile's `[ -e ]` skips it when the script is absent;
   - a possible fix is `[ -e "$$f" ] || [ -L "$$f" ]`, with a deliberate choice about dotfiles.
3. **An unreadable `domain/`** with the script present makes `os.listdir` (`validate-dsl.py:262`) raise. It fails
   closed (exit 1), but it isn't a reported problem.
4. **No test covers `dsl_active`'s `OSError` branch:** `domain` as a regular file, or an unreadable directory.
5. **Wording:**
   - `agents/implementer.md` says "before writing application code that depends on them", slightly weaker than
     R-6's "no application-code step starts";
   - `agents/code-reviewer.md` leaves out the "never below 0" that the review skill states.

Items carried over from 0012's backlog, deliberately out of scope here: `"dsl": 1.0`, `description` in R-3, the
recipe paste indent, `DSL_FILE_RE` anchoring, raw file names in output, and the draft insertion's fragility.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 38 | every AC met; the implementer wording is slightly weaker than R-6 |
| Security | 25 | 24 | no crash, hang or link path left; the unreadable-directory traceback fails closed |
| Test quality & test-first | 20 | 18 | a red commit before every step; the `OSError` branch is untested |
| Plan conformance | 10 | 10 | file by file, the deviation accurate |
| Maintainability | 5 | 5 | |
| **Total** | 100 | **95** | PASS needs ≥ 80, no BLOCKER, every AC met |
