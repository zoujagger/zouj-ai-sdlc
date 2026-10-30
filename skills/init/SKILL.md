---
name: init
description: Activates zouj-ai-sdlc in the current repo by scaffolding .aiops/, the Makefile contract, REVIEW.md, CLAUDE.md guidance and the CI gate audit, without overwriting existing files. Use once per repo, or when someone asks to set up or install the workflow here.
argument-hint: "[--stack python|node|go]"
disable-model-invocation: true
---

# Initialise this repo

1. Explain in two lines what will happen. Until `.aiops/` exists, every plugin hook here is a no-op. After init, code is read-only until an intent's plan is approved.
2. Run `sdlc init $ARGUMENTS`. It copies `templates/scaffold/` and keeps any file that already exists.
3. For each **kept** file (for example an existing `Makefile` or `CLAUDE.md`), show the human what the scaffold version adds, and offer to merge the relevant parts. A Makefile must expose `format lint typecheck test build check`.
4. Run `sdlc doctor` and relay what needs fixing.
5. Offer the optional allow-rules for unattended execution in state 4 (listed in `.aiops/README.md`). The human adds them to `.claude/settings.json` themselves, because guardrail config is human-owned.
6. Suggest committing the scaffold (`chore: adopt zouj-ai-sdlc`), then starting with `/zouj-ai-sdlc:intent "<first need>"`.
