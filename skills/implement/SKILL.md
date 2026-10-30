---
name: implement
description: State 4 EXECUTION, fully autonomous. After `Plan Approved`, executes every plan.md step on an isolated branch or worktree with strict TDD (proof test first, run it, see it fail, write code, iterate until lint, build and tests are green), ticking steps and logging deviations without asking the human. Use after `Plan Approved` or to resume execution.
argument-hint: "[intent-id] [step, e.g. S3]"
---

# State 4: EXECUTION (autonomous TDD)

Arguments: `$ARGUMENTS` (default: the active intent, first open step).

1. **Precondition.** `sdlc status` shows state 4, or state 5 with review findings to fix. If it doesn't, report the state and stop.
2. **Isolation.** Work on `feat/NNNN-slug`. If you're on `main`, create the branch (`git switch -c feat/NNNN-slug`). For parallel steps, use `/zouj-ai-sdlc:parallel` (git worktrees, max 3).
3. **Loop over the open steps, in order, without asking the human:**
   1. Mark the step `- [~]` and dispatch a fresh **implementer** subagent with only: the step text, its ACs, its Test definitions row, and the plan's Approach.
   2. When it returns, check the evidence: the red output is quoted, `make check` is green, the step is `[x]`, there's a commit with `Red:`/`Green:` lines, and any deviations are logged.
   3. If the evidence is missing, send the implementer back. If `make check` fails, iterate. Keep going until it's green.
4. **Escalate only when stuck.** Ask the human only for an unresolvable engine error (toolchain broken, environment missing, contradictory spec) or when the Steps must change (that voids the approval, so ask for `Plan Approved NNNN` again).
5. **Finish.** When every step is `[x]` and `make check` is green, run `sdlc status` (it shows state 5), then continue straight to `/zouj-ai-sdlc:review`.

The Stop hook re-runs `make check` and won't let you finish red. If permission prompts interrupt the loop, see `.aiops/README.md` → "Unattended execution" for the allow-rules the human can add.
