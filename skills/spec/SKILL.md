---
name: spec
description: State 2 SPECIFICATION. From an approved intent.md, writes spec.md, translating business goals into engineering requirements, testable acceptance criteria, DB schema, API contracts, and security and architectural data-leak flags. Then stops for `Spec Approved`. Use after `Intent Approved`.
argument-hint: "[intent-id]"
---

# State 2: SPECIFICATION → spec.md

Intent: `$ARGUMENTS` (default: active). The state is **read-only**: write only `.aiops/` and `docs/adr/`.

1. **Precondition.** `sdlc status $ARGUMENTS` must show state 2. If it doesn't, report the state and its next step, then stop.
2. **Draft.** Run `sdlc draft <id> spec`.
3. **Requirements.** Delegate to **product-analyst**: Summary, Requirements, **Acceptance criteria** (Given/When/Then, AC-1…). Ask for **3 to 5** concise, user-observable ACs (the happy path and the most important edge cases, never more than 7). HTTP codes, field validation, logging and schemas go into Requirements, Data model and API contracts, not into ACs.
4. **Domain model first (the `dsl` part).** If the dsl part is active (a `domain/*.dsl.json` file exists, or `sdlc list-installed` shows `dsl`), the architect formalizes the new business rules, state machines and workflows in `domain/<name>.dsl.json` terms in `## Domain DSL` (which `sdlc draft` adds) **before the Data model** and API contracts, and derives both from it. A purely technical or UI change writes `No domain changes` and why. `sdlc validate` requires the section while the part is active.
5. **Engineering.** Delegate to **architect**: **Data model** (DDL, migration reversibility, per-column data classification), **API contracts** (schemas, codes, errors, auth), **Architecture**, **Rollout & rollback**, plus ADR drafts for hard-to-reverse decisions.
6. **Security & data-leak flags.** Apply `policy-security` and `policy-compliance`. Every endpoint and data flow gets a check for authz/IDOR, cross-tenant access, and leaks through logs, errors, exports, caches and third parties. Each flag reads risk → mitigation → who decides. Set `risk: high` when the triggers apply.
7. **Validate.** Run `sdlc validate <id>`. Fix every error. With more than 5 ACs it warns that the scope may be too large; with more than 8 it refuses the Draft spec (and `approve` with it): consolidate the outcomes, or go back to the human about splitting the intent.
8. **Stop at the gate.** Present: the ACs, the schema and API summary, the **flags needing a decision**, open questions, and the risk. Then:
   > Review `.aiops/NNNN-slug/spec.md`. Resolve the flags above, or type **`Spec Approved NNNN`** (or, if signing needs your passphrase, run the printed `/usr/bin/python3 -I <plugin>/bin/sdlc approve NNNN spec` command in your terminal) to move to PLAN.

   For `risk: high`, say that the tech lead should review before approval. **Don't start planning until the gate opens.**
