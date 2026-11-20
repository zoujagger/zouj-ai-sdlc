---
id: 0011
title: Scope sizing: cap acceptance criteria per intent
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T14:07:41Z
approved-via: cli
approved-sha256: f954e0c5d4d6ff60558d3fbe0827192f6fb3829a1ef4a192636ee80014b5aa1d
---

# Spec: Scope sizing: cap acceptance criteria per intent

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements. The intent's open questions were accepted with its approval (the thresholds stay fixed). At spec
     review, zoujagger changed the error to say "Spec exceeds…" (it counts spec.md) and asked for the intent's own
     outcomes to be capped at 3-5 as well. Policy skills applied (security, compliance). -->

## Summary
Specs here grow to 15-30 ACs because nothing sizes an intent. This change works at two levels (intent: Desired
outcome):

- **Advice.** The `intent` and `spec` skills, the `product-analyst` agent and the artifact templates ask for 3 to 5
  high-level outcomes in `intent.md`'s `## Desired outcome`, and 3 to 5 user-observable ACs in `spec.md` (never
  more than 7). When the work won't fit, they ask the human to split it before `intent.md` exists, and the analyst
  flags it at the top of the intent. An epic is caught at the intent gate, not at the spec.
- **Enforcement.** `sdlc validate` counts the AC ids in `spec.md`'s `## Acceptance criteria`. Above 5 it warns.
  Above 8 it errors, but only while the spec's gate is closed. `approve` already refuses an artifact that doesn't
  validate, so an oversized Draft spec can't reach `Spec Approved`. Approved specs (0001-0009) get the warning at
  most, so history and CI stay green.

## Requirements
- **R-1: the count.** The number of **distinct** AC ids (`A.ac_ids`, so HTML comments are ignored and a repeated id
  counts once) in `spec.md`'s `## Acceptance criteria` section. Mentions elsewhere in the spec don't count. Only
  `spec.md` is counted: intent.md has no AC section (intent: Out of scope).
- **R-2: the thresholds** are fixed: `WARN_ACS = 5` and `MAX_ACS = 8`, as constants in `schema.py`. Nothing in
  config changes them (intent: Open questions, accepted).
- **R-3: 6 or more ACs → warning.** `` `## Acceptance criteria` has N criteria (more than 5): the scope may be too
  large for one intent; consider splitting it into smaller intents `` (one string, N filled in). It prints with the
  `!` prefix in `sdlc validate` and never changes the exit code.
- **R-4: 9 or more ACs while the gate is closed → error.** The text is exactly `Spec exceeds maximum of 8
  acceptance criteria; consolidate behavioral outcomes or split into smaller intents.` followed by
  ` (spec.md has N.)`. It states the reason and the procedure (CLAUDE.md rule 2). "Gate closed" is judged from the
  text being validated, as `machine.gate()` judges it on disk: `status` isn't `Approved`, or `approved-sha256`
  doesn't equal `A.approval_hash("spec", text)`. A spec edited after approval is closed again, so it errors.
  When the error applies, R-3's warning isn't also printed.
- **R-5: gate open → warning only.** An approved, unchanged spec with 9 or more ACs gets R-3's warning, never R-4's
  error. `sdlc validate --all` and `sdlc validate --all --ci` on this repo's `.aiops/` report no new error.
- **R-6: the check is a schema check.** It is registered as `scope_size` in `schemas/spec.json` `checks`. A check
  may now return `(errors, warnings)` as well as a plain list of errors, and `validate()` accepts both, so the
  existing checks are unchanged. The callers (`cmd_validate`, `doctor`, `approvals.approve`, the post-edit hook)
  are unchanged and pick it up through `validate()`.
- **R-7: the advice.**
  - `skills/intent/SKILL.md`:
    - Step 3 gets a **Scope check**: if the answers cover several separate user workflows, or would need more than
      5 high-level outcomes (or more than 5 observable ACs later), stop and ask the human (AskUserQuestion) whether
      to split the work into smaller intents that run one after another, before step 4 creates anything.
    - Step 4's delegation tells product-analyst the caps: **3 to 5** high-level outcomes in `## Desired outcome`
      (top-level bullets; detail goes in the spec), 3 to 5 ACs at spec time, and the callout rule.
  - `skills/spec/SKILL.md` step 3: product-analyst writes 3 to 5 concise, user-observable ACs (the happy path and the
    most important edge cases), and leaves HTTP codes, field validation, logging and schemas to Requirements, Data
    model and API contracts. Step 6 names the 5/8 rule.
  - `agents/product-analyst.md`:
    - **Intent cap:** 3 to 5 high-level, observable outcomes in intent.md's `## Desired outcome` (top-level
      bullets), after the same scope-split check as the skill's step 3.
    - **Strict cap:** 3 to 5 ACs per spec, never more than 7.
    - **Behavioural:** Given/When/Then about what the user observes, not the implementation.
    - **Epic warning:** when the scope can't fit in 5 ACs, a `> ⚠️ **Scope:** …consider splitting before approval`
      callout at the top of intent.md's body, under the title.
  - `templates/artifacts/intent.md`: comments naming the 3-5 outcome cap under `## Desired outcome` and the
    callout. The intent cap is advice only: no validator check counts intent bullets (R-1). `templates/artifacts/spec.md`: the AC comment
    names the 3-5 target and the 5/8 rule.
- **R-8: the docs.**
  - `docs/state-machine.md`'s Schemas table gets a `scope_size` row.
  - `CHANGELOG.md` `[Unreleased]` gets a `### Added` entry naming `.aiops/0011-scope-sizing/`.
- **Non-functional:** stdlib only; no change to the approval hash or to any gate; `make check` passes.

## Acceptance criteria
- **AC-1**: Given a spec whose `## Acceptance criteria` has 5 or fewer distinct AC ids, when `sdlc validate`
  runs, then it reports no scope warning or error.
- **AC-2**: Given a Draft spec with 6 to 8 AC ids, when `sdlc validate` runs, then it prints R-3's warning
  suggesting a split, and exits 0.
- **AC-3**: Given a spec with 9 or more AC ids whose gate is closed (Draft, or Approved and edited since), when
  `sdlc validate` runs, then it prints R-4's error and exits 1, and `sdlc approve` refuses it.
- **AC-4**: Given an approved, unchanged spec with 9 or more AC ids, when `sdlc validate` runs, then it prints only
  R-3's warning. `sdlc validate --all` on this repo reports no error for 0001-0010.
- **AC-5**: Given the shipped skills, agent and templates, then they state the scope-split check before intent.md
  is created (intent step 3, product-analyst), the 3-5 cap on intent outcomes (intent step 4, product-analyst,
  intent template), the 3-5 AC target with a cap of 7 and behavioural ACs (product-analyst, spec step 3), and the
  epic callout (product-analyst, intent template), and `make check` passes.

## Data model
None. No file format changes: the check reads `spec.md` and never writes it.

## API contracts
- `schema.validate()` keeps its signature and return value `(errors, warnings)`.
- A `CHECKS` entry may return a list (errors) or a tuple `(errors, warnings)`.
- `sdlc validate`'s output and exit codes are unchanged except for the new lines (R-3, R-4).

## Security & data-leak flags
- ⚠️ **No override.** A Draft spec above 8 ACs can't be approved, and no config or allowance lifts that. A human who
  wants a larger spec must split or consolidate it. This is the intended behaviour (intent: Open questions,
  accepted). (zoujagger)
- The check can only add errors. It can't open a gate, and it touches no secret, approval, lock or audit path.
  `--ci` runs it with the head's engine for the warning, and the base's engine in this repo's CI.

## Architecture
- `lib/sdlc_engine/schema.py`: `WARN_ACS`, `MAX_ACS`, `_scope_size(d, a, secs)`, registered in `CHECKS`.
  The gate test needs the raw text for the hash, so `validate()` passes it in: `a` already has it, or the check gets
  `text` through a small change to the check call. Which one is a plan decision.
- `machine.gate()` isn't reused: it reads the file on disk, and the post-edit hook and `validate(text=…)` judge a
  text that may differ.
- **Not taken:**
  - counting in intent.md (it has no AC section);
  - an error on every spec above 8 (7 approved specs here would fail CI);
  - surfacing the warning from the post-edit hook when there's no error (it only speaks on errors today; the skills
    run `sdlc validate`, which prints it).

## Rollout & rollback
- One PR. Adopting repos get the rule with the next plugin release. Their approved specs only warn, and a Draft spec
  above 8 ACs must be split or trimmed before approval.
- Rollback: revert the PR.

## Open questions
None. The intent's questions were settled: fixed thresholds (accepted with its approval), and the error says
"Spec exceeds…" (zoujagger at spec review, which changes the wording quoted in the intent's Desired outcome).
