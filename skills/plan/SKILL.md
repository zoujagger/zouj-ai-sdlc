---
name: plan
description: State 3 PLAN, a mandatory human gate. Strict read-only state - reads the codebase and writes only plan.md, a chronological file-by-file execution strategy with risks and test definitions - then halts for an explicit `Plan Approved` before any code can be written. Use after `Spec Approved`.
argument-hint: "[intent-id]"
---

# State 3: PLAN (read-only) → plan.md

Intent: `$ARGUMENTS` (default: active).

**You are in a strict read-only state.** The engine blocks writes to any file outside `.aiops/` and docs. That covers Edit and Write, redirects, `sed -i`, package installs, formatters, and `git add`/`commit` of code. Read, search, `git log`, and running the existing tests are allowed. You don't need Claude Code's Plan mode, because the engine enforces this state. If you do use Plan mode, exit it only to write plan.md.

1. **Precondition.** `sdlc status` shows state 3. If it doesn't, report and stop.
2. **Read.** Read `intent.md`, `spec.md`, the ADRs, and every file the change will touch. Delegate the drafting to the **planner** subagent (it runs `sdlc draft <id> plan`).
3. **Check what comes back:**
   - **Steps** are chronological and file-by-file. Each step is one TDD cycle naming its proof test and the ACs it covers.
   - **Risks** have mitigations.
   - **Test definitions** have at least one row per AC. `sdlc validate <id>` must pass.
4. **Stress test.** Ask the human the planner's 3 hardest questions (failure modes, rollback, test gaps). Revise plan.md from their answers.
5. **HALT.** Summarise the steps (count, files, risks), then say exactly:
   > Execution is locked. Review `.aiops/NNNN-slug/plan.md`, then type **`Plan Approved NNNN`** to unlock autonomous execution.

   **Don't execute anything** until the approval context confirms the gate opened.

| Red flag | Reality |
|---|---|
| "I'll scaffold the files so the plan is concrete." | Read-only. Put sketches in plan.md. |
| "They said 'looks good', that's approval." | Only the exact phrase `Plan Approved NNNN`, typed by the human, opens the gate. |
