---
name: parallel
description: Sets up 2-3 parallel Claude Code sessions, each in its own git worktree, for independent plan.md tasks. Use when plan.md marks tasks as parallelisable.
argument-hint: "<intent-id> <task-ids, e.g. T2 T3>"
disable-model-invocation: true
---

# /parallel: worktrees for parallel sessions

Arguments: `$ARGUMENTS`

1. Read the **Parallelisation** section of `plan.md`. Refuse more than 3 sessions in total: parallel work you can't review is the bottleneck, not throughput.
2. Check that the tasks don't touch the same files. If they overlap, warn the user and suggest running them in sequence.
3. For each task, run `scripts/worktree.sh <intent-id> <task-id>`. It creates `../<repo>-<id>-<task>` on branch `feat/<id>-<task>`.
4. Print, for each worktree: `cd <path> && claude "/implement <task-id> <intent-id>"`.
5. Remind the user: merge each branch back through a PR, and record any deviation in `plan.md` there.
