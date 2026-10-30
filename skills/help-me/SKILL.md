---
name: help-me
description: Maps a free-text goal ("I need to…", "how do I…", "what should I run for…") to the right zouj-ai-sdlc skill, agent or sdlc command given the current state, and explains why. Use when someone is unsure which command fits.
argument-hint: "<what you want to do>"
---

# Find the right command

Goal: `$ARGUMENTS`. If it's empty, ask one question about what they're trying to do.

1. Run `sdlc status`. The state decides the order: no approved intent → `/zouj-ai-sdlc:intent` first, whatever they asked for; a bug → `/zouj-ai-sdlc:fix`; a production issue → `/zouj-ai-sdlc:incident`. Docs-only changes (`*.md`, `docs/`) need no intent.
2. Answer in at most 8 lines:
   - **Run:** the exact command, with arguments filled in.
   - **Why:** one sentence tying it to their goal and state.
   - **Then:** the next 1-2 steps and the **human gate** they'll hit (the exact approval phrase).
   - If a hook will block part of the request (code in states 1-3, merging, a production deploy, locked tests), say so and give the procedure.
3. If nothing fits, say so plainly and suggest `/zouj-ai-sdlc:intent` to capture the need. Never invent commands.

Skills: intent · spec · plan · implement · review · pr · status · fix · init · parallel · deploy · triage · incident · postmortem · adr · learn · retro · release · security-check · onboard.
