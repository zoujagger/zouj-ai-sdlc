---
name: triage
description: Maintain stage. Turns an alert (control-band breach), ticket, or channel message into a read-only diagnosis and a draft intent.md that re-enters the SDLC. Use when monitoring fires or a support ticket arrives.
argument-hint: "<alert:<metric> | #issue | message text>"
---

# /triage: close the loop

Trigger: `$ARGUMENTS`

1. For metric alerts, run `python3 scripts/check-bands.py --metric <metric>` to confirm the band level deterministically:
   - **Band 1 (1σ):** just log it. Reply with the reading and stop.
   - **Band 2 (2σ):** read-only diagnosis (continue below).
   - **Band 3 (3σ):** diagnosis, plus either propose a fix PR or recommend the **pre-approved runbook** listed in `ops/bands.yaml` (e.g. rollback). A human runs it via the workflow.
2. Delegate to the **diagnostician** subagent. It writes a draft `docs/intents/NNNN-*/intent.md`.
3. Present the hypotheses and the recommendation. The **service owner** decides: fix now (→ `/spec`), schedule, or close.
4. For a SEV1 or SEV2 ongoing incident, switch to `/incident` instead.
