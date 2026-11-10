---
name: init
description: Activates zouj-ai-sdlc in the current repo by scaffolding .aiops/, the Makefile contract, REVIEW.md, CLAUDE.md guidance and the CI gate audit, without overwriting existing files. Use once per repo, or when someone asks to set up or install the workflow here.
argument-hint: "[--stack python|node|go]"
disable-model-invocation: true
---

# Initialise this repo

Prefer **`/zouj-ai-sdlc:setup`**: it does the same scaffold with prerequisite checks, a profile (`solo`, `team`,
`strict`), a preview, and the human steps. Use `init` directly only when the human asks for the bare scaffold.

1. Explain in two lines what will happen. The safety guards (secrets, force-push, deploys) already run in every repo, but the SDLC gates wait for `.aiops/`. After init, code is read-only until an intent's plan is approved.
2. Run `sdlc init $ARGUMENTS`. It copies the core scaffold from `templates/scaffold/` and keeps any file that already exists. The opt-in parts (`review`, `maintain`, `deploy`, `governance`, `issues`) are added with `--with <part>`, only when the human asks for one; the output names the parts left out.
3. For each **kept** file (for example an existing `Makefile` or `CLAUDE.md`), show the human what the scaffold version adds, and offer to merge the relevant parts. A Makefile must expose `format lint typecheck test build check`.
4. Run `sdlc doctor` and relay what needs fixing, including **approver signing**. Each approver configures SSH
   commit signing and adds their key to `.aiops/config/allowed-signers` (see `.aiops/README.md`). Never write that file
   yourself: it's human-owned. The profile is the human's too: they type `Setup Profile solo|team|strict` as their
   whole prompt (the state card says so while none is chosen).
5. Offer the optional allow-rules for unattended execution in state 4 (listed in `.aiops/README.md`). The human adds them to `.claude/settings.json` themselves, because guardrail config is human-owned.
6. Suggest committing the scaffold (`chore: adopt zouj-ai-sdlc`), then starting with `/zouj-ai-sdlc:intent "<first need>"`.
