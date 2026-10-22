---
name: onboard
description: Explains this repository and its intent-driven AI-native workflow to a new contributor. Use when someone is new or asks how the repo works.
---

# /onboard

1. Read `README.md`, `CLAUDE.md`, `docs/sdlc.md`, `REVIEW.md`, `docs/governance.md`, the `Makefile`, and `docs/adr/`, and list `docs/intents/`.
2. Explain in under 300 words: what the project does, the loop (Intent → Plan → Design → Build → Test → Deploy → Maintain), the human gates, the contract commands, and where the artifacts live.
3. Show the skills and agents per stage (the table in `docs/sdlc.md`), and the hooks that will block them and why.
4. Suggest a first step: `/sdlc` to see work in flight, or `/intent` for their first change.
