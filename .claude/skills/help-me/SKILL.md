---
name: help-me
description: Maps a free-text goal ("I need to…", "how do I…", "what should I run for…") to the right skill, agent, or make target in this repo, and explains why. Use when someone is unsure which command fits their task.
argument-hint: "<what you want to do>"
---

# /help-me: find the right command

Goal: `$ARGUMENTS`. If it's empty, ask what they're trying to do, in one question.

1. Read the candidates: the `name` + `description` front matter of `.claude/skills/*/SKILL.md` and `.claude/agents/*.md`,
   the README "Start here" table, and `make help`.
2. Check where they are: current branch, `docs/intents/` and the status of the matching intent (as `/sdlc` would).
   The workflow decides the order: no validated intent → `/intent` first, whatever they asked for (CLAUDE.md rule 1);
   a bug → `/fix`; a production issue → `/incident`. Docs-only, typos and dependency bumps need no intent.
3. Answer in at most 8 lines:
   - **Run:** the exact command, with arguments filled in from their goal.
   - **Why:** one sentence tying it to their goal and stage.
   - **Then:** the next 1-2 steps, and the human gate they will hit.
   - If a hook will block part of what they asked (production deploy, merging, editing locked tests), say so and give the procedure.
4. If nothing fits, say so plainly and suggest `/intent` to capture the need. Don't invent commands.
