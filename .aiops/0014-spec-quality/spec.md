---
id: 0014
title: Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene
status: Approved
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: 2026-11-20
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-20T19:21:43Z
approved-via: cli
approved-sha256: 90d8883c5518d5aba7fe2188a0b9a56c656ca40014a61141319bbeaea83eece4
---

# Spec: Sharper specs: N/A brevity, diagrams, AC traceability, query hygiene

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements. The intent's three questions were answered before its approval: guidance only, plus one check
     (the Mermaid line cap), and `None (no changes)` in the three implementation sections. -->

## Summary
The engineering half of a spec is where the human's review time goes. This change makes the architect write it
for a fast review (intent: Desired outcome):

- **Empty sections:** a section with no change says `None (no changes)` and nothing else.
- **A diagram:** a multi-step flow, a state transition or a new table gets one small Mermaid diagram.
- **Traceability:** every table, column and endpoint cites the AC that needs it.
- **Query hygiene:** stored data comes with its query patterns, composite indexes and N+1 prevention.

All of this is guidance in the architect agent, the spec skill and the spec template. One rule is enforced: a
Mermaid block of more than 12 lines in a draft spec fails `sdlc validate`.

## Requirements
- **R-1: N/A brevity.** When a spec changes nothing in `## Data model`, `## API contracts` or
  `## Rollout & rollback`, the architect writes exactly `None (no changes)` there and nothing else.
  `## Security & data-leak flags` and `## Architecture` never take it: they always show the reasoning, even when the
  conclusion is that nothing is at risk.
- **R-2: the diagram.** When the change introduces a multi-step data flow, a state transition or a DB table,
  `## Architecture` opens with one Mermaid block of at most 12 lines, of the fitting kind:
  - `sequenceDiagram` for a flow between components;
  - `flowchart` (or `stateDiagram-v2`) for states and decisions;
  - `erDiagram` for tables and relations.

  The prose that follows explains only what the diagram doesn't show. With none of the three triggers, no diagram.
- **R-3: the Mermaid cap, enforced.** A new spec check, `mermaid_size`:
  - A fenced block whose info string is `mermaid` (` ``` ` or `~~~`, three or more) with more than 12 non-blank
    lines between its fences is an error while the spec's gate is closed (0011's `_gate_open`), anywhere in the
    spec. HTML comments are stripped first. An unclosed fence counts to the end of the text.
  - The error states the reason and the procedure (CLAUDE.md rule 2):
    `` a ```mermaid block has N lines (more than 12): keep one diagram to the main flow, states or tables, and move
    detail into the prose ``.
  - Approved, unchanged specs are exempt.
- **R-4: AC traceability.** In `## Data model`, every table, column, index or migration change, and in
  `## API contracts`, every endpoint or event, ends with the `[AC-N]` id or ids it satisfies, for example
  `` - `GET /contacts.csv`: … [AC-1, AC-2] ``. A change that no AC needs is removed, or raised under
  `## Open questions` for the human. This is guidance, not checked.
- **R-5: query hygiene.** When `## Data model` adds or reads stored data, it ends with a **Queries** list. Each
  entry gives:
  - the query pattern (filter, sort, page);
  - the composite index that serves it, with the tenant key leading in multi-tenant data;
  - how N+1 is prevented (a join, a batched `IN` load, eager loading, or a single aggregate query);
  - the AC it serves.

  No database or ORM syntax is assumed; DDL may use the project's own. This is guidance, not checked.
- **R-6: where it's written:**
  - `agents/architect.md`: steps 3, 4, 6 and 7, plus a Rules line for R-1;
  - `skills/spec/SKILL.md`: step 5 (Engineering) and step 8 (the gate presentation names the diagram and the
    `[AC-N]` tags);
  - `templates/artifacts/spec.md`: comments in the four sections, with the placeholders kept so the existing
    placeholder warning still fires;
  - `docs/state-machine.md`: a `mermaid_size` row;
  - the CHANGELOG `[Unreleased]`: an entry naming `.aiops/0014-spec-quality/`.
- **R-7: what doesn't change.** The `## Domain DSL` order (0012) comes first, and the Data model and API contracts
  still follow from the model. The product-analyst's half of the spec, the schema's sections, and the other checks
  are unchanged.
- **Non-functional:** stdlib only; `make check` passes; every existing spec still validates.

## Acceptance criteria
- **AC-1**: Given a Draft spec with a ` ```mermaid ` block of 13 non-blank lines, when `sdlc validate` runs, then it
  fails with R-3's error naming 13. With 12 lines, an unrelated fenced block, or blank lines that bring the total
  over 12, it passes. An approved, unchanged spec with a long block passes, and an unclosed long fence fails.
- **AC-2**: Given the shipped architect agent and spec skill, then they say that `## Data model`,
  `## API contracts` and `## Rollout & rollback` read exactly `None (no changes)` when nothing changes, and that
  Security and Architecture never do.
- **AC-3**: Given the shipped architect agent, spec skill and spec template, then they require one Mermaid diagram
  (`sequenceDiagram`, `flowchart` or `erDiagram`, at most 12 lines) for a multi-step flow, a state transition or a
  DB table.
- **AC-4**: Given the same texts, then every table or column change and every endpoint cites its `[AC-N]`, and
  unrequested scope is removed or raised as an open question.
- **AC-5**: Given the same texts, then `## Data model` ends with Queries (patterns, composite indexes with the tenant
  key leading, N+1 prevention). `docs/state-machine.md` lists `mermaid_size`, and `make check` passes.

## Data model
None (no changes)

## API contracts
- `sdlc validate`: a new error line for a long Mermaid block (R-3) [AC-1]. Its output format and exit codes are
  unchanged.
- `schemas/spec.json`: `checks` gains `mermaid_size` [AC-1].

## Security & data-leak flags
- The check only reads the spec's text and can only add an error to a spec whose gate is closed. It opens no gate
  and touches no guard, approval or audit path.
- The fence scan is linear, with no backtracking regex. A spec is a file the agent writes, so the scan must not be
  steerable into a slow path; it is a single pass over the lines.
- The guidance adds query-hygiene and tenant-key advice, which strengthens the existing cross-tenant flag
  (`policy-security`) rather than replacing it.

No flag needs a decision.

## Architecture
- **`schema._mermaid_size(d, a, secs, text)`** (0011's signature):
  - returns `[]` when `_gate_open("spec", a, text)` holds;
  - otherwise strips comments with `A.COMMENT_RE`, walks the lines, and opens on a fence line matching
    `^\s{0,3}(`{3,}|~{3,})\s*mermaid\b`;
  - closes on a fence of the same character that is at least as long;
  - counts the non-blank lines in between, and returns one error per block over 12.
- **Registered** in `CHECKS` and in `schemas/spec.json` `checks`.
- **Guidance edits:** no code beyond the check.
- **Not taken:**
  - checking `[AC-N]` tags or `None (no changes)` with regexes over prose (the human chose guidance: brittle, false
    positives);
  - validating Mermaid syntax (intent: Out of scope);
  - limiting the check to `## Architecture` (a long diagram anywhere costs the same review time).

## Rollout & rollback
- One PR. Adopters get the guidance with the next release, and the check applies only to their draft specs.
- **Rollback:** revert the PR.

## Open questions
None.
