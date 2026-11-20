---
id: 0014
title: Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene
status: Approved
owner: zoujagger
initiator: zoujagger
source: request to make State 2 specs faster to review (2026-11-20)
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T19:19:05Z
approved-via: cli
approved-sha256: f6f406880fec3701ee23d714e2aaa6a2770a20bb48e748d56561bc47bba9d233
---

# Intent: Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene

<!-- State 1 BRAINSTORMING. Written from zoujagger's request on 2026-11-20. The scope check passed: 4 outcomes, one
     workflow (how State 2 writes spec.md). The three open questions were answered by zoujagger before approval:
     guidance only, plus one check (the Mermaid line cap); `None (no changes)` in the three implementation sections.
     Unknowns go in Open questions, never invented. approved-* fields are
     stamped by the human approval; agents never write them. -->

## Problem
The human reads every spec in full at the spec gate, and the engineering half is where review time goes:

- **Filler in empty sections.** When a change has no schema, API or rollout impact, the architect still writes
  prose in those sections, and the human reads it to find there is nothing there.
- **Data flows only as prose.** Multi-step flows, state transitions and new tables are described in paragraphs, so
  the human rebuilds the picture in their head.
- **Untraced design.** Tables, columns and endpoints in the Data model and API contracts don't say which AC needs
  them, so scope the human never asked for can slip into the design unnoticed.
- **Query performance left implicit.** Specs list a schema but not how it will be queried: the query patterns, the
  composite indexes they need (with the tenant key first in multi-tenant data), and how N+1 queries are avoided.
  These traps surface in review or production instead of at the gate.

The architect agent (`agents/architect.md`) and the spec skill (`skills/spec/SKILL.md`) ask for none of this today.

## Desired outcome
- **Explicit N/A brevity.** When a spec makes no schema, API or rollout change, the architect writes exactly
  `None (no changes)` in that section (`## Data model`, `## API contracts` or `## Rollout & rollback`), and nothing
  else. `## Security & data-leak flags` and `## Architecture` never take it: they always show the reasoning.
- **Visual architecture.** When a feature introduces a multi-step data flow, a state transition or a DB table,
  `## Architecture` includes one concise Mermaid diagram (`sequenceDiagram`, `flowchart` or `erDiagram`) of at most
  12 lines. `sdlc validate` enforces the cap: a ` ```mermaid ` block longer than 12 lines in a spec whose gate is
  closed is an error. This is the one deterministic check in this intent; the rest is guidance.
- **AC traceability.** Every table or column change and every API endpoint in `spec.md` cites the `[AC-N]` id(s) it
  satisfies, so nothing unrequested enters the engineering design.
- **Query hygiene.** When the Data model touches stored data, `## Data model` lists the expected query patterns, the
  composite indexes they need (the tenant key included and leading, where data is multi-tenant), and how N+1
  queries are prevented.

## Users & systems affected
- Users: the human approver at the spec gate; the agent in State 2 (architect, product-analyst); later states that
  read the spec (planner, reviewers).
- Systems: `agents/architect.md`, `skills/spec/SKILL.md`, `templates/artifacts/spec.md` (its guidance comments),
  possibly `lib/sdlc_engine/schema.py` and `schemas/spec.json` (see Open questions), `tests/`, and
  `docs/state-machine.md` if a check is added.

## Constraints
- **Domain-neutral and stack-neutral:** no database, framework or ORM is assumed. The query guidance names patterns
  and indexes, not a vendor's syntax.
- **One engine change:** the Mermaid line cap. It is test-first (CLAUDE.md rule 2), stdlib only, and leaves approved
  specs green, as 0011 and 0012 do. AC traceability, query hygiene and the N/A wording are guidance in
  `agents/architect.md`, `skills/spec/SKILL.md` and the spec template, with no prose regex.
- **No new required section:** the spec schema's sections stay as they are.
- **0012's `## Domain DSL` rules stand:** when the dsl part is active, the Data model and API contracts still follow
  from the model.

## Out of scope
- Rewriting existing specs (0001-0013) to the new style.
- Rendering or validating Mermaid syntax.
- Query-plan analysis, or any tooling that inspects a real database.
- Changes to the product-analyst's half of the spec (Summary, Requirements, ACs), which 0011 sized.

## Open questions
- [x] **Advice or checks?** Guidance for AC traceability, query hygiene and the N/A wording (no prose regex), plus
  one deterministic check: a ` ```mermaid ` block of more than 12 lines in a draft spec fails `sdlc validate`.
  (zoujagger, 2026-11-20)
- [x] **What counts as an "endpoint or table line"?** Moot: AC traceability is guidance only. (zoujagger,
  2026-11-20)
- [x] **Which sections take `None (no changes)`?** Only `## Data model`, `## API contracts` and
  `## Rollout & rollback`. Security and Architecture always show active reasoning. (zoujagger, 2026-11-20)
