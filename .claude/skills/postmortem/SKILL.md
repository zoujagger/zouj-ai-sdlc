---
name: postmortem
description: Drafts a versioned, blameless postmortem and closes the loop. Each incident becomes a regression eval, and larger action items become new intents. Use after an incident is resolved.
argument-hint: "<incident title>"
---

# /postmortem

1. Gather the timeline, impact, and root-cause notes from the conversation, the incident channel, or the user.
2. Delegate to **incident-responder** to write `docs/postmortems/YYYY-MM-DD-<slug>.md` from the template.
3. Check that it's blameless, that the contributing factors go beyond the trigger, and that every action item is typed (prevent/detect/mitigate) and owned.
4. **Close the loop:**
   - Add a regression eval: `evals/tasks/<slug>.yaml` with `source: incident:<postmortem path>` (`/learn` helps).
   - Detection gap? Propose a metric or band change in `ops/bands.yaml`.
   - Action items that need real work become draft `docs/intents/NNNN-*/intent.md` files.
5. Offer to create GitHub issues for the remaining small action items (`gh issue create`, which needs confirmation).
