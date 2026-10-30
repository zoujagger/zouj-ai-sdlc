---
name: incident
description: Guides live incident response with triage, runbook lookup, recent-change correlation, mitigation, and timeline. Use when something is broken in production.
argument-hint: "<symptom description>"
---

# /zouj-ai-sdlc:incident: respond

Symptom: `$ARGUMENTS`

1. Delegate to the **incident-responder** subagent.
2. Keep a UTC timeline in the conversation, and update it as the user reports actions.
3. Always recommend the safest mitigation first (rollback, or flag off). Never execute production changes. Provide the commands instead.
4. When it's resolved, offer `/zouj-ai-sdlc:postmortem`.
