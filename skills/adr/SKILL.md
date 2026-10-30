---
name: adr
description: Creates an Architecture Decision Record in docs/adr. Use when a significant or hard-to-reverse technical decision is being made.
argument-hint: "<decision title>"
---

# /zouj-ai-sdlc:adr: record a decision

Title: `$ARGUMENTS`

1. Next number: the highest `docs/adr/NNNN-*.md` + 1. Filename: `docs/adr/NNNN-kebab-title.md`.
2. Fill in `${CLAUDE_PLUGIN_ROOT}/templates/docs/adr.md` with context, decision, alternatives, and consequences, drawing on the conversation and the code (cite `path:line`).
3. `Status: Proposed`. If it supersedes an earlier ADR, link both ways (but don't edit the old decision text, just its status line).
4. Show the ADR and ask the user to confirm or adjust it.
