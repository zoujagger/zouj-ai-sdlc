---
name: verify
description: Final independent verification by the verifier subagent in a fresh context window, against spec.md ACs and plan.md. Use before declaring a change done or opening a PR.
argument-hint: "[intent-id]"
---

# /verify: fresh-context verification

Intent: `$ARGUMENTS` (or the `NNNN` in the branch name)

1. First make sure your own feedback loop is closed: `make check` is green in this session (the Stop hook enforces it). For UI work, attach a screenshot.
2. Delegate to the **verifier** subagent. Give it **only** the intent folder path and the base branch. Don't pass your own conclusions, so it doesn't inherit the session's assumptions.
3. Present its verdict as-is. If it's NOT VERIFIED, fix the gaps (logging any deviations in `plan.md`) and run `/verify` again.
4. When it's VERIFIED: next is `/review`, then `/pr`.
