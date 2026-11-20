---
id: 0013
title: Harden the dsl part: safe detection, validator edge cases, implement and review guidance
status: Approved
owner: zoujagger
initiator: zoujagger
source: 0012 review (.aiops/0012-dsl-part/review.md, MEDIUM finding and Backlog 1-3, 7) and the 0012 split (2026-11-20)
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T18:01:11Z
approved-via: cli
approved-sha256: 3f5eb4a35a9486831f90d961b3dcfeeeb9d11665e9b449d294cd9a881c4e34dc
---

# Intent: Harden the dsl part: safe detection, validator edge cases, implement and review guidance

<!-- State 1 BRAINSTORMING. Written from zoujagger's request on 2026-11-20, which merges the 0012 review's
     pre-release findings with the second half of the 0012 split (implement and review). The scope check passed:
     4 outcomes, all about the one `dsl` part. The three open questions were answered by zoujagger before approval:
     the Makefile keys on the script or a model file, the hardcoding check is reviewer guidance, and each confirmed
     case is a MEDIUM finding. Unknowns go in Open questions, never invented. approved-* fields are
     stamped by the human approval; agents never write them. -->

## Problem
0012 shipped the opt-in `dsl` part on main (PR #26). It hasn't been released yet, and its review found problems to
fix before release (`.aiops/0012-dsl-part/review.md`):

- **False activation on a repo's own `domain/`.** The part is active whenever a top-level `domain/` directory
  exists (0012 R-5, R-6). Many Go, Python and DDD repos already have a `domain/` source folder. After `upgrade`,
  their `make check`, which every Stop hook runs, fails with "scripts/validate-dsl.py is missing", and every new
  spec requires `## Domain DSL`, though they never asked for the part (review: MEDIUM).
- **Validator edge cases** (review: LOW ×3):
  - a non-string `kind`, or a non-string transition `from`/`to`, raises `TypeError` with a traceback instead of a
    reported problem;
  - membership checks against lists make a model O(n²): a 1 MiB file is estimated at 40-70 s in every Stop hook;
  - a symlinked `domain/` passes the Makefile's `[ -d domain ]` but the validator prints "skipped" and exits 0, so
    the models are never validated.
- **The second half of 0012's split isn't done.** Implementation and review don't know about the model:
  - nothing tells State 4 to bring `domain/` up to date before application code;
  - nothing in State 5 checks that rules and transitions declared in `domain/` aren't hardcoded again in
    controllers or UI components.

## Desired outcome
- **Safe detection.** An empty or non-DSL `domain/` directory never activates the dsl checks:
  - the spec's `domain_dsl` check is active only when install-state's `parts` names `dsl`, **or** at least one
    `domain/*.dsl.json` file exists;
  - the `validate-dsl` target in `make check` runs the validator only when `scripts/validate-dsl.py` (the part's
    own file) **or** at least one `domain/*.dsl.json` file exists. It reads no JSON, so it needs no Python to decide.
    The second case, model files without the script, fails with the `sdlc setup --with dsl` hint, as today.
- **A hardened validator** (`scripts/validate-dsl.py`):
  - a non-string `kind` or transition `from`/`to` is a reported problem, never a traceback;
  - lookups use sets, so validation stays linear on large models;
  - a symlinked `domain/` is reported as a problem (exit 1), never silently skipped.
- **Implementation follows the model.** While the part is active, State 4 (`implement`) updates and validates
  `domain/*.dsl.json` (`make validate-dsl`) before it changes application code.
- **Review checks for hardcoded rules.** While the part is active, State 5 (`review`) checks that the state
  transitions and business rules declared in `domain/*.dsl.json` aren't hardcoded in application controllers or UI
  components:
  - It works through explicit guidance in the `review` skill and the code-reviewer agent: the reviewer inspects
    that code for the model's states, events and rule conditions and judges each hit. There is no static scanner.
  - Each confirmed case is a **MEDIUM** finding. It lowers the score and is listed clearly, but doesn't block the
    verdict on its own.

## Users & systems affected
- Users: adopters with their own `domain/` directory (no longer affected unless they opt in); teams using the `dsl`
  part; the agent in states 4 and 5; the human reading the review.
- Systems: `lib/sdlc_engine/lifecycle.py` (`dsl_active`), `lib/sdlc_engine/schema.py` (`domain_dsl`), the core
  Makefile template and `defaults/scaffold-history.json`, `templates/scaffold/scripts/validate-dsl.py`,
  `skills/implement`, `skills/review`, `agents/implementer.md`, `agents/code-reviewer.md`, the docs that describe
  activation (`domain/README.md`, the READMEs, `docs/state-machine.md`, `docs/architecture.md`, the CHANGELOG), and
  `tests/`.

## Constraints
- **Before the next release.** 0012 is on main but unreleased. Installs pin to tags, so no adopter has the false
  activation yet.
- Engine and scaffold changes are test-first (CLAUDE.md rule 2); stdlib only (Python ≥ 3.9).
- Activation can still only *add* requirements, and install-state still never decides a gate (threat model).
- 0012's accepted decisions stand: the exemption for approved specs, `--with all` leaving `dsl` out, `domain/` not
  protected, and advisory enforcement (no new guard).
- The Makefile can't read install-state's JSON without Python, so its detection keys on files, the script or a
  model, and differs in form from the engine's, which reads install-state.

## Out of scope
- 0012 review Backlog items 4-6, 8 and 9: `"dsl": 1.0`, `description` in R-3, the recipe paste indent,
  `DSL_FILE_RE` anchoring, raw file names in output, and the draft insertion's fragility. They can be a later intent.
- A hard pre-edit guard against application-code edits before `domain/` (0012 decided advisory enforcement).
- A deterministic static scanner for hardcoded rules (see Open questions).
- Code generation from the model.

## Open questions
- [x] **The Makefile's detection:** run the validator only when `scripts/validate-dsl.py` or at least one
  `domain/*.dsl.json` file exists, with no Python snippet reading install-state. (zoujagger, 2026-11-20)
- [x] **The hardcoding check:** explicit guidance in the `review` skill and the reviewer agent, with no static
  scanner script. (zoujagger, 2026-11-20)
- [x] **The severity:** each confirmed hardcoded rule or transition is a **MEDIUM** finding; it lowers the score
  without being a blocker on its own. (zoujagger, 2026-11-20)
