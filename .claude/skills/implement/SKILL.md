---
name: implement
description: Build stage. Implements the next (or a named) task from an accepted plan.md with TDD, verifies with make check, and keeps plan.md in sync, logging deviations in the same commit. Use when coding planned work.
argument-hint: "[T<n>] [intent-id]"
---

# /implement: build from plan.md

Arguments: `$ARGUMENTS`

1. Find the intent (an argument, or the `NNNN` in the branch name) and the task (an argument, or the first unchecked task in `plan.md`).
2. **Precondition.** `plan.md` is `Accepted` or `In Progress`. If it isn't, stop and run `/plan` first. Set it to `In Progress` and mark the task `[~]`.
3. Delegate to the **implementer** subagent with the task text, its ACs, and the plan's Approach.
4. When it returns, check that:
   - `make check` is green.
   - the task is ticked, and any divergence from the plan is recorded in the **Deviation log in the same commit** (`git show --stat HEAD` includes `plan.md` when there's a deviation).
5. Report the outcome. Next: the next task, or `/verify` once all tasks are done.

Routine, well-tested tasks can run in auto mode. Review the artifacts (diff, plan.md, test results) at the end of the session.
