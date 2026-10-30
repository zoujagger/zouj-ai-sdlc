---
id: 0001
title: zouj-ai-sdlc plugin
status: Draft
owner: zoujagger
initiator: zoujagger
source: free text (Claude Code session, 2026-10-30)
created: 2026-10-30
---

# Intent: zouj-ai-sdlc plugin

## Problem
The repo is a copy-me template. Consumers fork it, so improvements never reach them, and most SDLC rules are
advisory skills that an agent can skip: it can mark its own artifacts approved, or write code before a plan exists.

## Desired outcome
An installable Claude Code plugin, `zouj-ai-sdlc`, inspired by Superpowers and modeled on Anthropic's AI-Native
SDLC Playbook. It automates state transitions across the lifecycle by enforcing the creation and validation of
human-readable, machine-actionable Markdown artifacts versioned in Git:
1 BRAINSTORMING (intent.md) → 2 SPECIFICATION (spec.md) → 3 PLAN, read-only (plan.md) → 4 EXECUTION, autonomous TDD
→ 5 PRE-REVIEW (review.md + PR description). Each gate is a human decision the agent cannot take.

## Users & systems affected
- Users: engineers and product owners using Claude Code; reviewers/CODEOWNERS
- Systems: Claude Code plugin system (skills, agents, hooks, bin/), git, GitHub Actions in consumer repos

## Constraints
- Claude Code only for v1; skills stay tool-neutral Markdown
- Dependencies stay git, make, python3 (pyyaml for evals), with gh and jq optional
- The current repo's live hooks guard themselves; the cutover is applied by the human from an external terminal

## Out of scope
- Cursor / OpenCode adapters
- Hosting a public marketplace listing

## Open questions
- [ ] Should `risk: high` specs require a second (tech-lead) approval? (zoujagger)
- [x] Rename the GitHub repo from ai-native-sdlc-template to zouj-ai-sdlc? → **Yes**: github.com/zoujagger/zouj-ai-sdlc, local dir renamed (zoujagger, 2026-10-30)
