---
name: spec
description: State 2 SPECIFICATION. From an approved intent.md, writes spec.md, translating business goals into engineering requirements, testable acceptance criteria, DB schema, API contracts, and security and architectural data-leak flags. Then stops for `Spec Approved`. Use after `Intent Approved`.
argument-hint: "[intent-id]"
---

# State 2: SPECIFICATION → spec.md

Intent: `$ARGUMENTS` (default: active). The state is **read-only**: write only `.aiops/` and `docs/adr/`.

1. **Precondition.** `sdlc status $ARGUMENTS` must show state 2. If it doesn't, report the state and its next step, then stop.
2. **Draft.** Run `sdlc draft <id> spec`.
3. **Requirements.** Delegate to **product-analyst**: Summary, Requirements, **Acceptance criteria** (Given/When/Then, AC-1…).
4. **Engineering.** Delegate to **architect**: **Data model** (DDL, migration reversibility, per-column data classification), **API contracts** (schemas, codes, errors, auth), **Architecture**, **Rollout & rollback**, plus ADR drafts for hard-to-reverse decisions.
5. **Security & data-leak flags.** Apply `policy-security` and `policy-compliance`. Every endpoint and data flow gets a check for authz/IDOR, cross-tenant access, and leaks through logs, errors, exports, caches and third parties. Each flag reads risk → mitigation → who decides. Set `risk: high` when the triggers apply.
6. **Validate.** Run `sdlc validate <id>`. Fix every error.
7. **Stop at the gate.** Present: the ACs, the schema and API summary, the **flags needing a decision**, open questions, and the risk. Then:
   > Review `.aiops/NNNN-slug/spec.md`. Resolve the flags above, or type **`Spec Approved NNNN`** to move to PLAN.

   For `risk: high`, say that the tech lead should review before approval. **Don't start planning until the gate opens.**
