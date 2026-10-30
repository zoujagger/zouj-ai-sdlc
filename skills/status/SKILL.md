---
name: status
description: Shows where an intent is in the 5-state lifecycle (BRAINSTORMING, SPECIFICATION, PLAN, EXECUTION, PRE-REVIEW) and the exact next step, from the state engine. Use when the user asks "what's next", "status of 0003", or starts work.
argument-hint: "[intent-id]"
---

# Lifecycle status

Run `sdlc status $ARGUMENTS`. With no id and no active intent, it prints a table of all intents.
Relay the card as-is: the state, who it's waiting on (agent or human), the gates, step progress, deviations, open questions, and the **next step**.
If it's waiting on the human, quote the exact approval phrase they need to type. Don't offer to do it for them.
For machine-readable output: `sdlc status <id> --json`.
