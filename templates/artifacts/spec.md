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
<!-- Testable, with ids. Every AC must appear in plan.md Test definitions and in review.md. -->
- **AC-1**: Given <context>, when <action>, then <observable outcome>.

## Data model
<DB schema changes as DDL or a table: entities, columns, types, constraints, indexes. Migration is
reversible? Data classification per column (public / internal / personal / secret).>

## API contracts
<Endpoints/events: method, path, request and response schemas, status codes, errors, auth, versioning.>

## Security & data-leak flags
<!-- Flag every place data could leak or be abused. Each flag: risk → mitigation → who decides. -->
- ⚠️ <e.g. tenant isolation on GET /contacts/:id: authz check by tenant_id> (owner)

## Architecture
<Components, data flow, cited code (path:line), alternatives considered and why not, ADRs needed.>

## Rollout & rollback
<Feature flag, migration order, the one rollback command, metrics to watch.>

## Open questions
- [ ] <Question> (who decides)
