---
name: learn
description: Captures institutional memory. When the agent makes the same mistake twice, a review finding recurs, or an incident occurs, adds a concise lesson to CLAUDE.md and a regression eval. Use after corrections, recurring review findings, or postmortems.
argument-hint: "<what went wrong>"
---

# Make the mistake not happen again

Input: `$ARGUMENTS`

1. Pick the weakest mechanism that will reliably work:
   - **CLAUDE.md → Lessons** (this repo): a convention or gotcha. One imperative, specific line.
   - **`.aiops/config/*`** (this repo; human-owned): a path to protect, a test glob, or a read-only exemption. Draft the line and let the human apply it.
   - **The plugin** (skill, schema or guard in zouj-ai-sdlc): a rule that should hold in every repo. Draft an issue or PR for the plugin repo instead of patching locally.
2. Keep CLAUDE.md at about one page. Move detail into `docs/` and leave a pointer.
3. Add a regression eval that would have caught it: `evals/<slug>/prompt.md` plus `evals/<slug>/graders/*.md` (the `claude plugin eval` format).
4. Show the diff for approval.
