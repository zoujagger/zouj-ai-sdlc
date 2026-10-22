---
name: spec
description: Design stage. Produces spec.md, with requirements and design in one session, from a validated intent.md, applying the policy skills and surfacing flags and policy conflicts. Use after an intent is validated, before any planning or code.
argument-hint: "<intent-id>"
---

# /spec: requirements + design in one session

Folder: `docs/intents/$ARGUMENTS-*/`

1. **Precondition.** `intent.md` has `status: Validated`. If it doesn't, stop and say the product owner gate is pending.
2. **Requirements.** Delegate to **product-analyst**: stories, testable ACs with IDs, edge cases, NFRs.
3. **Design.** Delegate to **architect**: approach, interfaces and data, alternatives, security, rollout and rollback, ADR drafts.
4. **Policies.** Make sure `policy-security`, `policy-compliance`, `policy-ux`, and `policy-brand` were applied. Each policy gets its section filled in or marked N/A.
5. **Surface.** List the **Flags** and **Policy conflicts** explicitly, each with the person who has to decide. Set `risk: high` if the compliance high-risk triggers apply.
6. Front-end work: suggest producing a mock-up from `intent.md` (e.g. Claude Design) and linking it in the UX section.
7. Present the summary. **Gate:** the product owner accepts (`status: Accepted`), resolving flags with the compliance owner, plus the tech lead if `risk: high`. Acceptance triggers `/plan $ARGUMENTS` in Plan mode.
