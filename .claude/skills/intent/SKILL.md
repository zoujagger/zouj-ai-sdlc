---
name: intent
description: Entry point of the AI-native SDLC. Turns a need (free text, GitHub issue, alert, or postmortem action) into a validated intent.md through framing questions. Use whenever someone describes a new feature, change, problem, or bug that has no intent yet.
argument-hint: "<need in plain words | #issue | alert:<metric>>"
---

# /intent: the trigger

Input: `$ARGUMENTS`

Everything starts here. No spec, plan, or code is written without an intent (typos, docs, and dependency bumps excepted).

1. **Gather the source.** For `#N`, run `gh issue view N`. For `alert:<metric>`, read `ops/bands.yaml` and the latest `scripts/check-bands.py` output. Otherwise use the text.
2. **Check for duplicates.** Search `docs/intents/*/intent.md` for the same problem. If one exists, offer to extend it.
3. **Ask framing questions** (at most 5, one round, most important first). Cover whatever is unclear among:
   - What problem, for whom, and what evidence?
   - What outcome would tell us this is done?
   - Which users and systems are affected?
   - Constraints (deadline, compliance, compatibility, performance)?
   - What's explicitly out of scope?
4. **Create the folder** with `scripts/new-intent.sh <kebab-slug>`, then delegate to the **product-analyst** subagent to fill in `intent.md` from the answers. Don't invent answers. Unknowns go in Open questions.
5. Show the intent. Ask the initiator to correct it. Remind them of the **gate**: the product owner sets `status: Validated` (or approves the intent PR in the shared repo).
6. Next: `/spec NNNN`.
