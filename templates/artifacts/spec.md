---
id: NNNN
title: <Title>
status: Draft          # Draft → Approved (human types `Spec Approved NNNN`)
risk: low              # low | medium | high (high: involve the tech lead before approving)
intent: ./intent.md
created: YYYY-MM-DD
---

# Spec: <Title>

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering
     requirements, DB schema and API contracts. Policy skills applied (security, compliance, UX, brand). -->

## Summary
<One paragraph: what changes for whom, and why (link the intent's desired outcome).>

## Requirements
- **R-1**: <functional requirement>
- Non-functional: performance · reliability · observability · accessibility

## Acceptance criteria
<!-- Testable, with ids. Every AC must appear in plan.md Test definitions and in review.md.
     3 to 5 user-observable ACs (never more than 7): `sdlc validate` warns above 5 and refuses a Draft spec above 8.
     Technical detail (codes, validation, logging, schemas) goes in Requirements, Data model, API contracts. -->
- **AC-1**: Given <context>, when <action>, then <observable outcome>.

## Data model
<!-- Exactly `None (no changes)` when nothing changes. Otherwise end each table, column or migration line with its
     [AC-N]; when stored data is added or read, close with Queries: pattern → composite index (tenant key first
     where multi-tenant) → N+1 prevention → [AC-N]. -->
<DB schema changes as DDL or a table: entities, columns, types, constraints, indexes. Migration is
reversible? Data classification per column (public / internal / personal / secret).>

## API contracts
<!-- Exactly `None (no changes)` when nothing changes. Otherwise end each endpoint or event with its [AC-N]. -->
<Endpoints/events: method, path, request and response schemas, status codes, errors, auth, versioning.>

## Security & data-leak flags
<!-- Flag every place data could leak or be abused. Each flag: risk → mitigation → who decides. -->
- ⚠️ <e.g. tenant isolation on GET /contacts/:id: authz check by tenant_id> (owner)

## Architecture
<!-- Never `None (no changes)`. A multi-step flow, a state transition or a DB table: open with one mermaid diagram
     (sequenceDiagram, flowchart or erDiagram), at most 12 lines; `sdlc validate` refuses a longer one. -->
<Components, data flow, cited code (path:line), alternatives considered and why not, ADRs needed.>

## Rollout & rollback
<!-- Exactly `None (no changes)` when nothing ships differently. -->
<Feature flag, migration order, the one rollback command, metrics to watch.>

## Open questions
- [ ] <Question> (who decides)
