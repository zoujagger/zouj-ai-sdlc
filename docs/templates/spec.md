---
id: NNNN
title: <Intent title>
status: Draft          # Draft | In Review | Accepted | Implemented | Superseded
owner: <product owner>
accepted_by:
risk: low              # low | high → high adds the tech lead to the gate
intent: ./intent.md
created: YYYY-MM-DD
---

# Spec: <Intent title>

<!-- Requirements AND design, produced in one session from intent.md, with the policy skills applied. -->

## Summary
<One paragraph: what changes for whom, and why (link the intent's desired outcome).>

## Requirements
### User stories
- **US-1**: As a <role>, I want <capability> so that <benefit>.

### Acceptance criteria
<!-- Testable, with IDs. Referenced by plan.md tasks and by tests. -->
- **AC-1** (US-1): Given <context>, when <action>, then <observable outcome>.

### Edge cases & errors
- <Case> → <expected behavior>

### Non-functional requirements
- Performance · Reliability · Observability (metrics to add to `ops/bands.yaml`?) · Accessibility

## Design
### Approach
<Components, responsibilities, data flow. Cite existing code as path:line. Add a mermaid diagram if useful.>

### Interfaces & data
<APIs, events, schemas, migrations (reversible?).>

### Alternatives considered
| Option | Why not |
|---|---|

### Security (policy-security)
<Data classification, threats (STRIDE-lite), authz model.>

### Compliance (policy-compliance)
<Personal data, retention, processors, audit, accessibility obligations.>

### UX & brand (policy-ux, policy-brand)
<Mock-up link, states (empty/loading/error/success), copy.>

### Rollout & rollback
<Feature flag, staged rollout, rollback command, the metrics to watch.>

## Flags (points of attention)
<!-- Anything the reviewer must look at: assumptions, risks, unknowns. -->
- ⚠️ <flag> (who decides)

## Policy conflicts
<!-- Where requirements clash with a policy skill. Resolved by the product owner + compliance owner. -->
| Requirement | Policy | Conflict | Resolution |
|---|---|---|---|

## Out of scope
- <...>

## ADRs
- <docs/adr/NNNN-...>
