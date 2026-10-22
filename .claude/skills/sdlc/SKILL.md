---
name: sdlc
description: Shows where an intent is in the AI-native SDLC (Intent → Plan → Design → Build → Test → Deploy → Maintain) and the exact next step. Use when the user asks "what's next", "status of 0003", or starts work on something.
argument-hint: "[intent-id]"
---

# /sdlc: stage status and next step

Target: `$ARGUMENTS`. If it's empty, list every `docs/intents/*` with its stage in one table, and stop.

1. Resolve `docs/intents/<id>-*/`.
2. Work out the stage from the artifacts and their `status:` front matter:
   | Condition | Stage | Next |
   |---|---|---|
   | no `intent.md` | Intent | `/intent` |
   | intent `Draft` | Intent: gate pending | product owner validates (`status: Validated`) |
   | no `spec.md` | Design | `/spec <id>` |
   | spec not `Accepted` | Design: gate pending | resolve Flags and Policy conflicts, then accept (tech lead too if `risk: high`) |
   | no `plan.md`, or plan `Draft` | Build: planning | `/plan <id>` (Plan mode), engineer accepts |
   | unchecked plan tasks | Build | `/implement` (or `/parallel` if marked parallelisable) |
   | all tasks done, not verified | Test | `/verify <id>` |
   | verified, no PR / PR open | Deploy | `/review` → `/pr`, then a CODEOWNER approves |
   | merged, not deployed to prod | Deploy | `/deploy` (staging), then the human prod approval |
   | spec `Implemented` | Maintain | watch `ops/bands.yaml`. Alerts → `/triage` |
3. Print a compact card: stage, gate status (who's being waited on), task progress (x/y), the number of deviation-log entries, open questions and flags, and the **exact next command**.
