---
name: learn
description: Captures institutional memory. When Claude makes the same mistake twice, a review finding recurs, or an incident occurs, adds a concise lesson to CLAUDE.md and a regression eval. Use after corrections, recurring review findings, or postmortems.
argument-hint: "<what went wrong>"
---

# /learn: make the mistake not happen again

Input: `$ARGUMENTS`

1. Classify where the fix belongs (the weakest mechanism that will reliably work):
   - **CLAUDE.md → Lessons:** a convention or gotcha. One line, imperative, specific.
   - **Skill** (`.claude/skills/...`): a multi-step procedure or domain knowledge that needs applying consistently.
   - **Hook** (`.claude/hooks/...`): an absolute rule that must never be broken. Hooks are human-owned, so draft the change and ask a human to apply it.
2. Draft the change. Keep CLAUDE.md at about one page. If it's getting long, move detail into a skill or `docs/` and leave a pointer.
3. Add a regression eval in `evals/tasks/<slug>.yaml` that would have caught it (`source: lesson` or `source: incident:<postmortem>`).
4. Show the diff for approval. Changes to CLAUDE.md, skills, or hooks trigger the eval suite in CI.
