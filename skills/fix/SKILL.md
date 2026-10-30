---
name: fix
description: Bug-fix lane. Captures the bug as a compact intent, spec and plan (one gate each, so three short approvals), then writes the failing test first, has the human confirm it, locks the tests with `sdlc lock`, and fixes the code without touching tests. Use for any bug report or regression.
argument-hint: "<bug description | #issue>"
---

# Bug fix: failing test first, then locked tests

Bug: `$ARGUMENTS`

1. **Intent (state 1).** Read the issue (`gh issue view` for `#N`) and the code, read-only. Run `sdlc new fix-<slug>` and `git switch -c fix/NNNN-<slug>`. Fill in intent.md: the symptom, evidence, expected behaviour, and **suspected cause**. Ask for `Intent Approved NNNN`.
2. **Spec (state 2).** A compact spec.md with **AC-1**: "Given <repro>, when <action>, then <correct behaviour>" (plus a regression AC if needed). Use "No change" in Data model and API contracts where that's true, and keep the data-leak flags. Ask for `Spec Approved NNNN`.
3. **Plan (state 3).** plan.md with **S1**: the failing test (its file and name), **S2**: the fix (files). Ask for `Plan Approved NNNN`.
4. **Red (state 4).** Write ONE failing test that reproduces the bug. Run it and show that it fails *for the right reason*.
5. **Human confirms the test.** Ask: "Does this test capture the bug correctly?" Wait for an explicit yes.
6. **Lock.** Run `sdlc lock`. From then on, test files (the `test-paths` globs) are read-only.
7. **Green.** Fix the production code only, and run `make check`. The Stop hook releases the lock once it's green. Never try to unlock it yourself (`sdlc unlock` is human-only).
8. Tick S1 and S2, commit `fix: ...` with `Refs: .aiops/NNNN-slug`, then go to `/zouj-ai-sdlc:review`. If the bug reached production, suggest `/zouj-ai-sdlc:learn` for a regression eval.
