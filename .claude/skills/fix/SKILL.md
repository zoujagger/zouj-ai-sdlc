---
name: fix
description: Bug-fix flow with a test lock. Write a failing test that reproduces the bug, have a human approve it, lock the tests, then fix the code without touching tests. Use for any bug report or regression.
argument-hint: "<bug description | #issue>"
---

# /fix: test first, then lock, then fix

Bug: `$ARGUMENTS`

1. **Understand.** Read the issue (`gh issue view` if `#N`) and the code. State the suspected cause.
2. **Red.** Write ONE failing test that reproduces the bug. Run `make test` and show that it fails *for the right reason*.
3. **Human approval.** Show the test and ask: "Does this test capture the bug correctly?" Wait for an explicit yes.
4. **Lock the tests.** Use the **Write tool** to create `.claude/state/test-lock` containing the test file path(s) and the approver's name. Shell writes to the lock are blocked.
   From now on the `guard-tests.sh` hook blocks every edit to test files (globs in `.claude/test-paths`).
5. **Green.** Fix the production code only. Run `make check`.
6. **Unlock.** The Stop hook removes the lock automatically once `make check` passes. If you're stuck, explain why. Never try to remove the lock yourself.
7. Commit `fix: ...` with `Refs:` the issue/intent. If this bug came from production, suggest adding it as a regression eval (`/learn`).
