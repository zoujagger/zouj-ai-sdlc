---
id: 0012
verdict: PASS   # PASS | CHANGES_REQUESTED (the human still decides the merge)
commit: 05e793f23e500ff6b274964ba872b4192ce2e673
score: 89/100
reviewers: verifier, code-reviewer, security-reviewer
created: 2026-11-20
---

# Review: Opt-in dsl part: a validated domain/ model for specs and plans

<!-- State 5 PRE-REVIEW. Written from the report of one fresh-context reviewer covering the three personas, who got
     only the intent folder and the base branch `main` (6e709aa). -->

## Summary
- **The part:** an opt-in `dsl` part (`domain/README.md` and a stdlib validator, `scripts/validate-dsl.py`),
  installed only by name and never through `all` or the legacy fallbacks.
- **The Makefile:** `make check` runs `validate-dsl` and skips it while there's no `domain/`.
- **The spec:** while the part is active, `## Domain DSL` is required in specs whose gate is closed, and the spec
  and plan skills model the domain first.

No guard, gate, approval or audit path changes. **PASS, 89/100**: every AC is met, and there is no BLOCKER and no
CRITICAL/HIGH finding.

The reviewer recommends fixing three LOW validator robustness issues before a release, and asks the human to decide
on one MEDIUM compatibility issue: activation by a bare `domain/` directory (Plan conformance; Backlog 1-3 and 7).

The reviewer ran, without writing anything:
- the targeted tests: `test_dsl` 34, `test_lifecycle` 18, `test_setup` 3 and `test_cli` 13 passed, and
  `DomainDsl`/`ScopeSizing` passed;
- `bin/sdlc validate --all`: 0 errors across 11 intents;
- `scaffold-history.py --check`: up to date;
- in-memory probes of the validator.

## Spec conformance
| AC | Verdict | Evidence (test, path:line) |
|---|---|---|
| AC-1 | ✅ met | `tests/test_setup.py::Apply::test_with_dsl_installs_the_part` (`:205`), `::test_with_all_leaves_dsl_out` (`:230`); `tests/test_lifecycle.py::DslPart` (`:868`: a legacy state with no `parts`, an edited config without state, upgrade and repair `--dry-run` planning no `domain/`, `init --with all` without dsl); the Compat test, now `LEGACY_PARTS`. Code: `lib/sdlc_engine/lifecycle.py:104-107`, `:148`, `:225`, `:229`, `:284` |
| AC-2 | ✅ met | `tests/test_dsl.py::ValidateDsl` (`:75-174`): every kind valid, the skip, invalid JSON, header, kind and key errors, a duplicate key, state references, a duplicate pair, a missing or unknown `initial`, a duplicate state, rules, workflow, a duplicate name across files, a link, more than 1 MiB, and depth |
| AC-3 | ✅ met | `tests/test_dsl.py::MakeCheck` (`:188-226`: no domain passes, valid passes, invalid fails, a domain without the script fails naming `sdlc setup --with dsl`); `tests/test_lifecycle.py::Detected::test_wired_makefile_keeps_recipes_with_validate_dsl` (`:440`). The S6 manual run wasn't done (logged); these tests cover it |
| AC-4 | ✅ met | `tests/test_engine.py::DomainDsl` (`:756-819`: inactive, active by state, active by directory, accepted and rejected bodies, a legacy state not active, an approved spec exempt and required again after an edit); `tests/test_cli.py::…::test_draft_spec_adds_domain_dsl_when_active` (`:250`) |
| AC-5 | ✅ met | `tests/test_cli.py::Docs::test_dsl_guidance` (`:1010`); `make check` 559 OK (Deviation log, S6) |

## Security
Nothing reaches HIGH:
- Guards, protected paths and the audit and approval paths are unchanged.
- Install-state and `domain/` can only add the `domain_dsl` requirement.
- The S4 exemption needs `_gate_open` (`status: Approved` and a matching hash), which the agent can't forge.

Each item below is a problem file or link the agent itself writes. In state 4 the agent can already edit the
Makefile, so none of them gains a privilege:
- [LOW] `templates/scaffold/scripts/validate-dsl.py:222`, `:174`: an unhashable value (`"kind": ["x"]`, or a
  transition `"from": ["s"]` with a valid event) raises `TypeError` with a traceback. The run fails closed (exit 1),
  but this breaks R-4 ("reported, never raised"). → Check `isinstance(..., str)` before membership and the `pairs`
  set, and test it.
- [LOW] `validate-dsl.py:135`, `:147`, `:170`, `:204`, `:207`: membership tests on lists make a file O(n²).
  Measured: 20k states take 1.2 s; a 1 MiB file is extrapolated at about 40-70 s, and the number of files is
  unbounded, in every Stop hook. → Keep a set beside each list (or cap entries or files).
- [LOW] `validate-dsl.py:236` vs the Makefile: a symlinked `domain` directory passes `[ -d domain ]` and
  `dsl_active`, but the validator prints "skipped" and exits 0, so the models aren't validated. → Report a symlinked
  directory as a problem and exit 1.

## Plan conformance
- S1-S6 are done and the file set matches. All 9 deviations are accurate and justified, checked one by one:
  - S1: the test reinterpretations and the `parts_line` change;
  - S2: `compile()` and the `check-bands.py` fix;
  - S3: the fixture fix;
  - S4: the exemption, confirmed by the human, and the `_gate_open` extraction;
  - S5: the unchanged docs;
  - S6: the manual run that wasn't done.
- **S4 is implemented correctly:** `_domain_dsl` returns early when `_gate_open("spec", a, text)` holds, and the
  test shows that an edit after approval brings the requirement back.
- **Leaks into old repos:** no path leaks `dsl` into an old repo. Every "every part" fallback is covered
  (`lifecycle.py:225`, `:229`, `:284`), and `adopt` goes through `installed_parts`. `parts_on_disk` finds `dsl` only
  from a file byte-equal to one the plugin wrote.
- **[MEDIUM, compatibility; follows the approved spec] Activation by a bare `domain/`.** R-5/R-6 assume that only
  `--with dsl` creates `domain/`, but many Go, Python and DDD repos have a top-level `domain/` source directory.
  After `upgrade` replaces their untouched or wired Makefile:
  - `make check` (and so every Stop hook) fails with "scripts/validate-dsl.py is missing";
  - every new spec requires `## Domain DSL`.

  Recommendation: key the Makefile and `dsl_active` on `domain/*.dsl.json` (or `domain/README.md`) rather than the
  bare directory, or at least name the behaviour in the CHANGELOG's upgrade notes. That needs a spec change and the
  human's decision.

## Test-first evidence
Each of S1-S5 has a commit touching only `tests/` before its code commit:

| Step | Red | Green |
|---|---|---|
| S1 | 89bc343 | 236c239 |
| S2 | b31efb9 | ff35b9b |
| S3 | a5e2976 | ac70fab |
| S4 | aae3d56 | 1245628 |
| S5 | 00241b0 | 81d7604 |

The tests are behavioural and assert exact output lines. Gaps: no test covers unhashable values, a size or entry
bound, or a symlinked `domain/`.

## Backlog (not blocking)
1. Validator: no `TypeError` on a non-string `kind` or `from`/`to` (Security, LOW).
2. Validator: sets for membership, and optionally a cap on files or entries (Security, LOW).
3. Validator: a symlinked `domain` is a problem, not a skip (Security, LOW).
4. Reject `"dsl": 1.0`. Align R-3 and the README on `description` for workflow steps and at the top level.
5. `setup.makefile_dsl_step` prints recipe lines with 7 leading spaces before the tab, so a verbatim paste gives
   make a "missing separator" error. Print them without the indent, or say to keep the tab.
6. `schema.DSL_FILE_RE` also matches `src/domain/x.dsl.json` and `my-domain/x.dsl.json`; anchor it with
   `(?<![\w/-])domain/` if those shouldn't count.
7. Revisit activation by a bare `domain/` (Plan conformance, MEDIUM), or document it in the upgrade notes.
8. Model file names are printed raw: control characters reach the Stop-hook output, and a non-UTF-8 name can raise
   on print.
9. `cli.cmd_draft`'s single `replace` on `"\n## Data model\n"` would silently do nothing if the template heading
   changed.

## Score
| Dimension | Weight | Score | Notes |
|---|---|---|---|
| Spec conformance | 40 | 37 | every AC met; small departures from R-3 (`1.0`, `description`) |
| Security | 25 | 21 | three LOW robustness gaps in a Stop-hook script; no privilege gained |
| Test quality & test-first | 20 | 18 | a red commit before every code step; no tests for unhashable values, size or symlinked directories |
| Plan conformance | 10 | 9 | all deviations logged and justified; the manual S6 run wasn't done |
| Maintainability | 5 | 4 | the draft insertion and the pasted recipe indent are fragile |
| **Total** | 100 | **89** | PASS needs ≥ 80, no BLOCKER, every AC met |
