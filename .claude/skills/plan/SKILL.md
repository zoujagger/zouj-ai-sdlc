---
name: plan
description: Build stage, step 1. Produces plan.md from intent.md and an accepted spec.md using Claude Code Plan mode, has the engineer stress-test it, and commits it once accepted. Use after spec acceptance and before writing code.
argument-hint: "<intent-id>"
---

# /plan: Plan mode → plan.md

Folder: `docs/intents/$ARGUMENTS-*/`

1. **Preconditions.** `spec.md` has `status: Accepted`. If it doesn't, stop and say which gate is pending.
2. **Plan mode.** If the session isn't in Plan mode, ask the engineer to switch (Shift+Tab, or start with `claude --permission-mode plan`). Don't edit code while planning.
3. Read `intent.md`, `spec.md`, the ADRs, and the code involved. Delegate the task breakdown to the **planner** subagent.
4. **Stress test.** Show the plan and ask the engineer to challenge it. Suggest 3 hard questions yourself: failure modes, migration and rollback, test gaps, parallelisation conflicts. Revise until they accept it.
5. Write `plan.md` from `docs/templates/plan.md` with `status: Accepted` and `engineer: <name>`. Fill in **Stress test** and **Parallelisation**.
6. Suggest a branch (`feat/$ARGUMENTS-<slug>`). If tasks can run in parallel, suggest `/parallel`. Next: `/implement`.

Rule for the rest of the build: **when code diverges from plan.md, update plan.md (tasks + Deviation log) in the same commit.**
