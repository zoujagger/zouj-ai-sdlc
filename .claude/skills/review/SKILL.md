---
name: review
description: Local review of the current branch per REVIEW.md in three passes (bugs, security, conformance to spec.md and plan.md). Use before opening a PR.
argument-hint: "[base-branch]"
---

# /review: REVIEW.md passes

Base: `$ARGUMENTS` (default `main`)

1. Collect `git diff <base>...HEAD` and any uncommitted changes. Find the linked `docs/intents/NNNN-*/`.
2. Delegate to the **code-reviewer** subagent (Passes 1 and 3). For Pass 2, delegate to **security-reviewer** when the diff touches auth, input, data, infra, CI, or dependencies.
3. Present the findings exactly in REVIEW.md format. Offer fixes for BLOCKER and MAJOR items, and apply only the ones the user confirms. Log any resulting divergence from the plan in `plan.md`.
4. If a finding has come up before, suggest `/learn` to turn it into a CLAUDE.md lesson plus an eval.
