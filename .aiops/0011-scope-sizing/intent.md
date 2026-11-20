---
id: 0011
title: Scope sizing: cap acceptance criteria per intent
status: Approved
owner: zoujagger
initiator: zoujagger
source: request to stop epics from passing as one intent (2026-11-20)
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T13:57:26Z
approved-via: cli
approved-sha256: 513aa04b1c7d9e60c2794886637b150e93cfdc3b534060a939e1209d35266e99
---

# Intent: Scope sizing: cap acceptance criteria per intent

<!-- State 1 BRAINSTORMING. Written from zoujagger's request on 2026-11-20 and two answers given in the session:
     the rule counts spec.md ACs (intent.md has no AC section), and the hard limit applies only while the spec's
     gate is closed. Unknowns go in Open questions, never invented. approved-* fields are stamped by the human
     approval; agents never write them. -->

## Problem
Nothing in the plugin keeps an intent small. An intent that is really an epic produces a spec with 15 to 30
acceptance criteria, and that has three costs:

- **Review fatigue.** The human reads and approves every AC at the spec gate, and then again in the plan and the
  review, which must reference each AC id (`covers_spec_acs`).
- **A long test-first phase.** Each AC needs a test definition and a verdict, so execution and review grow with the
  AC count.
- **No signal to split.** The skills and agents never ask whether the work should be split. Neither does the
  validator.

Evidence in this repo: 7 of the 9 specs have more than 8 ACs. 0002 has 29, and 0004, 0007 and 0009 have 23 each.
Only 0008 (6) and 0010 (7) are close to the target size.

## Desired outcome
- **The interview sizes the scope.** When the requirements cover several separate user workflows, or would need
  more than 5 observable ACs, the `intent` skill stops before creating `intent.md` and asks the human whether to
  split the work into smaller intents that run one after another.
- **The analyst writes small, behavioural specs.** `product-analyst` aims for 3 to 5 user-observable ACs per spec
  (the happy path and the most important edge cases), and never more than 7. Technical detail (HTTP codes, field
  validation, logging, schemas) goes into the spec's Requirements, Data model and API contracts sections, not into
  ACs. When the scope can't fit in 5 ACs, the analyst puts a prominent "consider splitting" callout at the top of
  the intent before the human reviews it.
- **`sdlc validate` enforces the size:**
  - more than 5 AC ids in `spec.md`: a warning that suggests splitting the intent;
  - more than 8: the error "Intent exceeds maximum of 8 acceptance criteria; consolidate behavioral outcomes or
    split into smaller intents.", but only while the spec's gate is closed. The agent has to fix it before the
    human's spec gate.
- **History stays green.** Approved specs above 8 ACs (0001-0009) get the warning at most, so
  `sdlc validate --all --ci` keeps passing on main and in CI.

## Users & systems affected
- Users: the human approver (fewer ACs to review per gate); the agent running `intent` and `spec` (must size and
  split); adopters of the plugin (the new rule reaches their repos through upgrade).
- Systems: `skills/intent/SKILL.md`, `skills/spec/SKILL.md` if it delegates AC writing, `agents/product-analyst.md`,
  `templates/artifacts/intent.md` and `spec.md` (guidance comments), the validator (`lib/sdlc_engine/schema.py`,
  `schemas/spec.json`), the post-edit schema hook (it runs the same `validate`), `tests/`, and `docs/state-machine.md`
  (the Schemas check table).

## Constraints
- Engine and guards are test-first (CLAUDE.md rule 2): the failing tests come before the `lib/` change. The tests
  cover ≤ 5 (valid), 6-8 (warning) and > 8 (error while Draft; warning only once Approved).
- Stdlib only. No change to the approval hash: the check reads the artifact and never writes it.
- `make check` stays green, and so does `sdlc validate --all --ci` against the existing `.aiops/`.

## Out of scope
- Splitting or rewriting the existing oversized specs (0001-0009).
- Adding an `## Acceptance criteria` section to `intent.md`. ACs stay in `spec.md`.
- A configurable threshold per repo. The 5/8 limits are fixed in this intent (see Open questions).

## Open questions
- [ ] Should the thresholds (5 warn, 8 error) be configurable in `.aiops/config.json`, or stay fixed? Fixed is the
  default here. (zoujagger)
- [ ] Should the error message say "Spec" rather than "Intent", since it counts the ACs in spec.md? The request's
  wording ("Intent exceeds…") is kept for now. (zoujagger)
