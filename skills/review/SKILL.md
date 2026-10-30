---
name: review
description: State 5 PRE-REVIEW, the final human gate. Runs fresh-context secondary personas (verifier, code-reviewer, security-reviewer) against the branch to verify spec.md compliance and catch vulnerabilities, then writes review.md (scoring report) and pr.md (PR description). Leaves the merge decision to the human. Use when all plan steps are done.
argument-hint: "[intent-id] [base branch, default main]"
---

# State 5: PRE-REVIEW → review.md + pr.md

Arguments: `$ARGUMENTS`.

1. **Precondition.** `sdlc status` shows state 5 and `make check` is green. Commit any outstanding work first, because the review is pinned to a commit.
2. **Secondary personas, in fresh contexts and in parallel.** Give each **only** the intent folder and the base branch. Never pass your own conclusions.
   - **verifier**: AC → test evidence, `make check` and `make build` results.
   - **code-reviewer**: bugs, spec and plan conformance, test-first evidence, scores.
   - **security-reviewer**: exploit paths, whether the spec's data-leak flags are mitigated, security score.
3. **Write review.md.** Run `sdlc draft <id> review`. Fill it in from the persona reports only: per-AC table, security findings, plan conformance, test-first evidence, and the **Score** table. Set `commit:` to `git rev-parse HEAD`.
   - `verdict: PASS` only if the total is ≥ 80, there are no BLOCKER or CRITICAL/HIGH findings, and every AC is ✅.
   - Otherwise use `CHANGES_REQUESTED`, list the fixes, and go back to `/zouj-ai-sdlc:implement` (then review again).
4. **Write pr.md** from `${CLAUDE_PLUGIN_ROOT}/templates/artifacts/pr.md` into the intent folder: summary, ACs with tests, deviations, risks and rollback, review score.
5. Run `sdlc validate <id>`, commit `.aiops/` (`docs(aiops): review NNNN`), and check that `sdlc status` reads "waiting for the human merge decision".
6. **Hand over.** Show the verdict, the score table and any findings, then say:
   > The final decision is yours. Open the PR with `/zouj-ai-sdlc:pr` if you want it, then review and merge it yourself.

   **Never merge, approve or push to main.** Hooks block those.
