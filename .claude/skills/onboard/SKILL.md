---
name: onboard
description: Interactive tour of this repository and its intent-driven AI-native workflow, tailored to the person's role and the repo's setup state. Use when someone is new, asks how the repo works, or asks where to start.
---

# /onboard

1. **Setup state.** Run `make doctor`. If it reports ✗ items or unwired Makefile targets, open with those and their fix commands:
   nothing else works well until `make check` actually checks something.
2. **Role.** Ask (AskUserQuestion) which hat they wear: product owner, engineer, service owner / SRE, or maintainer of this template.
3. **Explain in under 250 words**, for that role only:
   - The loop (Intent → Plan → Design → Build → Test → Deploy → Maintain) and the **gates they own** (`docs/governance.md` → Human gates).
   - The 3-5 commands they will actually use, from the README "Start here" table:
     | Role | Commands |
     |---|---|
     | Product owner | `/intent`, `/sdlc`, validating `intent.md`, accepting `spec.md` |
     | Engineer | `/sdlc`, `/plan`, `/implement`, `/fix`, `/verify`, `/review`, `/pr` |
     | Service owner / SRE | `/triage`, `/incident`, `/postmortem`, `/deploy`, `ops/bands.yaml` |
     | Maintainer | `make doctor`, `make validate-template`, `/learn`, `/retro`, `make evals` |
   - Which hooks may block them and why (`README.md` → Guardrails). A block always states the procedure.
4. **Show, don't tell.** Point to the worked example in `docs/examples/` (a complete `intent.md` → `spec.md` → `plan.md`), and list `docs/intents/` (work in flight).
5. **First step.** Offer one concrete action: run `/sdlc` if intents exist, otherwise offer to start `/intent` with them now.
   If they're unsure what they need, suggest `/help-me "<what you want>"`.
