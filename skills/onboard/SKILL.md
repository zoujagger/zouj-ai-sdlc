---
name: onboard
description: Interactive tour of the zouj-ai-sdlc workflow (5 states, human gates, enforcement hooks) tailored to the person's role and this repo's setup state. Use when someone is new, asks how the workflow works, or asks where to start.
---

# Onboarding

1. **Setup.** Run `sdlc doctor`. If the repo isn't initialized, offer `/zouj-ai-sdlc:init` first. If the Makefile contract is unwired, say so: state 4 can't prove anything until `make check` checks something.
2. **Role.** Ask (AskUserQuestion) which hat they wear: product owner, engineer, reviewer / CODEOWNER, or service owner / SRE.
3. **Explain in under 250 words**, for that role only:
   - The machine: 1 BRAINSTORMING → 2 SPECIFICATION → 3 PLAN (read-only) → 4 EXECUTION (autonomous) → 5 PRE-REVIEW, with artifacts in `.aiops/NNNN-slug/`.
   - **Their gates.** Product owner: `Intent Approved` and `Spec Approved`. Engineer: `Plan Approved`. Reviewer: the merge. These are typed as the whole prompt, and the agent can never produce them.
   - What a hook will block and why (code before `Plan Approved`, self-approval, merging, prod deploys, locked tests). Every block states the procedure.
4. **Show.** Run `sdlc status` (work in flight), and point to the worked example in `${CLAUDE_PLUGIN_ROOT}/docs/examples/`.
5. **First step.** Offer one concrete action: resume the active intent at its next step, or start `/zouj-ai-sdlc:intent` now.
