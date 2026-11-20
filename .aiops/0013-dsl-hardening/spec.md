---
id: 0013
title: Harden the dsl part: safe detection, validator edge cases, implement and review guidance
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T18:05:48Z
approved-via: cli
approved-sha256: 29a747490cd161561e88a3b5339bab22d3110a4f542236ae4c01003d0b03760e
---

# Spec: Harden the dsl part: safe detection, validator edge cases, implement and review guidance

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements. The intent's three questions were answered before its approval: the Makefile keys on the script
     or a model file, the hardcoding check is reviewer guidance, and each confirmed case is a MEDIUM finding.
     Risk is low: detection only narrows, the validator only reports more, and the rest is guidance. -->

## Summary
This fixes what 0012's review found before release, and adds the implement and review half of the 0012 split
(intent: Desired outcome):

- **Detection keys on the model, not on the directory.** The engine's `dsl_active` and the Makefile's
  `validate-dsl` no longer treat a bare `domain/` as the part. A repo's own `domain/` source folder no longer gets
  a failing `make check` or a new spec requirement.
- **The validator never raises on bad input.** It stays linear on large models, and it reports a symlinked
  `domain/` instead of skipping it.
- **State 4 brings the model up to date first**, and State 5 looks for rules and transitions hardcoded in
  controllers and UI. Each confirmed case is a MEDIUM finding.

## Requirements
- **R-1: the engine's detection.** `lifecycle.dsl_active(root)` is true when install-state's `parts` list names
  `dsl` (unchanged), or `<root>/domain` holds at least one `*.dsl.json` entry. A bare, empty or non-DSL `domain/`
  doesn't count.
  - Both `domain_dsl` (spec check) and `sdlc draft <id> spec` use it, so both follow.
  - 0012's exemption for approved, unchanged specs stays.
- **R-2: the Makefile's detection.** The core template's `validate-dsl` recipe, still called by `check`:
  - when `scripts/validate-dsl.py` exists, it runs `python3 scripts/validate-dsl.py domain`. The validator skips
    a missing `domain/` itself (exit 0) and reports a symlinked one (R-4).
  - otherwise, when a `domain/*.dsl.json` file exists, it fails with
    `[validate-dsl] domain/*.dsl.json found but scripts/validate-dsl.py is missing: run sdlc setup --with dsl`.
  - otherwise it prints `[validate-dsl] no dsl part - skipped` and passes.

  It reads no JSON and uses only POSIX `sh` tests (`[ -f … ]`, a `for` loop over the glob with an existence check),
  with no `ls` parsing. `scaffold-history.json` is regenerated. Wiring (`cli.wire`) and `upgrade` of a wired
  Makefile keep working.
- **R-3: the validator never raises on a value's type.** Every reference is checked to be a string before any
  lookup:
  - `kind`, transition `from`/`to`, `initial`, every `final` entry, `start`, and every `next` entry;
  - otherwise the problem is reported at its JSON path, for example `$.kind: expected text (state_machine, rules or
    workflow)` or `$.transitions[0].from: expected a state name`, never a `TypeError`;
  - a transition with a non-string `from` or `event` is left out of the duplicate-pair check.
- **R-4: a symlinked `domain/`.** When the model directory is a link, the validator prints
  `domain: a link, not followed (validate the real directory)` and exits 1. A missing directory is still skipped
  (exit 0), and a regular file named `domain` is skipped as "no domain/".
- **R-5: linear lookups.** States, step ids, rule ids, transition pairs and model names are checked against sets,
  so each file is O(n). A model with 80,000 states is validated in well under the Stop hook's patience (the test's
  bound is 10 s).
- **R-6: implement guidance.** `skills/implement/SKILL.md` and `agents/implementer.md`: while the dsl part is
  active, and the spec's `## Domain DSL` names model files, no application-code step starts until those
  `domain/*.dsl.json` changes are made and `make validate-dsl` is green. Plan S1 normally does this (0012). If
  application code needs a rule or state the model doesn't declare, update the model first and log a deviation;
  never hardcode it.
- **R-7: review guidance and severity.** `skills/review/SKILL.md` and `agents/code-reviewer.md`: while the dsl part
  is active, the code-reviewer reads the model files and inspects the diff's application controllers, handlers and
  UI components for hardcoded copies of the model's state transitions and business rules: state names compared or
  assigned as literals, transition tables or `switch`/`if` chains on events, and rule conditions or limits
  repeated as literals. It judges each hit.
  - Each confirmed case is a **MEDIUM** finding, written as `[MEDIUM] path:line: <transition or rule id>
    hardcoded → read it from the model (domain/<name>.dsl.json)`.
  - Findings go under a `## Domain model` section in review.md, which the skill adds while the part is active.
  - Each confirmed case takes **3 points** off Spec conformance (never below 0). By itself it doesn't change the
    verdict rule: PASS still needs ≥ 80, no BLOCKER or CRITICAL/HIGH, and every AC met.
  - A literal that only names a state for display, or a test fixture, isn't a finding.
- **R-8: the docs.** Every text that says the part is active "when `domain/` exists" now says "when a
  `domain/*.dsl.json` file exists". That covers `domain/README.md` (the scaffold), the spec and plan skills, the
  architect and planner, `cli.DOMAIN_DSL_SECTION`, the `_domain_dsl` messages, `README.md`,
  `templates/scaffold/.aiops/README.md`, `docs/state-machine.md`, `docs/architecture.md`, and the unreleased
  CHANGELOG entry for 0012 (0012 hasn't been released, so its entry is corrected rather than followed by a
  "Fixed" entry).
- **Non-functional:** stdlib only; Python 3.9; `make check` passes; no guard, gate or audit change.

## Acceptance criteria
- **AC-1**: Given a repo whose `domain/` holds no `*.dsl.json` (empty, or `domain/user.py`) and whose install-state
  doesn't name `dsl`, when `sdlc validate` and `sdlc draft <id> spec` run, then a spec without `## Domain DSL`
  passes and the draft has no such section. Given a `domain/x.dsl.json` or `dsl` in install-state, then both act
  as in 0012.
- **AC-2**: Given the scaffold Makefile, when `make check` runs:
  - with neither the script nor a model file (a non-DSL `domain/` included), it passes with the skip line;
  - with the script and a valid model, it passes; with an invalid one, it fails;
  - with a model file but no script, it fails naming `sdlc setup --with dsl`.

  A Makefile wired by detection keeps its recipes through `upgrade`.
- **AC-3**: Given model files with a non-string `kind`, `from`, `to`, `initial`, `final` entry, `start` or `next`
  entry, when the validator runs, then it exits 1 with each problem at its JSON path and no traceback. Given a
  symlinked `domain/`, it exits 1 with the link line. Given a model with 80,000 states, it finishes in under 10 s.
- **AC-4**: Given the shipped implement skill and implementer agent, then they say that, while the dsl part is
  active, the `domain/*.dsl.json` changes and a green `make validate-dsl` come before application code, and that a
  missing rule goes into the model first.
- **AC-5**: Given the shipped review skill and code-reviewer agent, then they describe the hardcoding inspection
  (controllers and UI, the model's transitions and rules), the MEDIUM severity, the 3-point deduction and the
  `## Domain model` section. The docs describe activation by model files, and `make check` passes.

## Data model
None. The model format (`domain/*.dsl.json`, `"dsl": 1`) is unchanged.

## API contracts
- **Engine:** `lifecycle.dsl_active(root)` has the same signature and a narrower meaning (R-1).
- **`scripts/validate-dsl.py`:**
  - same arguments, output format and exit codes;
  - new problem lines (R-3, R-4);
  - a symlinked directory now exits 1 instead of 0.
- **Make:** `validate-dsl` and `check` names unchanged; the skip line's text changes (R-2).
- **review.md:** an optional `## Domain model` section. `schemas/review.json` is unchanged, since extra sections
  are allowed.

## Security & data-leak flags
- ⚠️ **Removing the model files lifts the requirement in CI**, as removing `domain/` did in 0012. With activation
  keyed on `*.dsl.json`, deleting or renaming them turns `domain_dsl` off where install-state isn't read.
  - Mitigation: the deletion is a visible diff, and locally install-state keeps the requirement on.
  - Decided in 0012: `domain/` stays unprotected. (zoujagger)
- ⚠️ **The validator still runs in every Stop hook** on agent-written files. This change removes its remaining
  crash path (R-3) and its quadratic cost (R-5), and stops it from passing silently on a link (R-4). The number of
  model files stays unbounded; each is still capped at 1 MiB and 64 levels. (zoujagger)
- The review guidance only reads code. No personal data, secrets or network access.

## Architecture
- **`lifecycle.dsl_active`:** `any(p.name.endswith(".dsl.json") for p in (root / "domain").iterdir())`, guarded for
  a missing or unreadable directory, after the install-state test.
- **`validate-dsl.py`:**
  - a `text()`-style guard before each lookup;
  - each list check gains a parallel set;
  - `main` checks `os.path.islink(folder)` before `isdir`.
- **The Makefile recipe:**

  ```sh
  if [ -f scripts/validate-dsl.py ]; then python3 scripts/validate-dsl.py domain;
  else found=; for f in domain/*.dsl.json; do [ -e "$f" ] && found=1; done;
    if [ -n "$found" ]; then echo "...missing: run sdlc setup --with dsl"; exit 1;
    else echo "[validate-dsl] no dsl part - skipped"; fi; fi
  ```

  `$$` is escaped for make.
- **The review section** is added by the skill, not by `sdlc draft`, because it applies only while the part is
  active.
- **Not taken:**
  - reading install-state in the Makefile (the human chose files only);
  - a static scanner for hardcoding (the human chose guidance);
  - a per-file count cap (the size cap and linear checks are enough for now).

## Rollout & rollback
- One PR before the next release. 0012 and 0013 ship together, so no adopter ever sees the bare-`domain/`
  activation.
- **Rollback:** revert the PR, which brings back 0012's detection. Don't release in that state.

## Open questions
- [x] Is a 3-point Spec-conformance deduction per confirmed hardcoding case the right size? **Yes** (R-7): it
  lowers the score noticeably, and a review with seven cases or more drops toward the 80 threshold. (zoujagger,
  2026-11-20)
