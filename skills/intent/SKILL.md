---
name: intent
description: State 1 BRAINSTORMING, the entry point. Turns a raw prompt, feature idea, GitHub issue, alert or postmortem action into .aiops/NNNN-slug/intent.md through a targeted clarification interview, then stops for the human's `Intent Approved`. Use whenever someone describes a new feature, change, problem or bug that has no intent yet.
argument-hint: "<need in plain words | #issue | alert:<metric>>"
---

# State 1: BRAINSTORMING → intent.md

Input: `$ARGUMENTS`

You are in a **read-only** state. Only `.aiops/` and docs can be written.

1. **Locate.** Run `sdlc status`. If an intent already covers this need, offer to continue that one (`sdlc use NNNN`) instead of creating a new one.
2. **Gather the source.** For `#N`, run `gh issue view N`. For `alert:<metric>`, read `ops/bands.yaml` and run `python3 scripts/check-bands.py --metric <metric>`. Otherwise, use the text as given.
3. **Clarification interview (targeted).** If the need is ambiguous, ask **at most 5 questions in one round** (use AskUserQuestion when the options are clear), most decision-relevant first. Cover only what's unclear:
   - the problem, who has it, and the evidence
   - the observable outcome that means "done"
   - the users and systems affected (data, integrations, tenants)
   - constraints: deadline, compliance, compatibility, performance
   - what's explicitly out of scope

   If an answer is still unknown, record it under **Open questions**. **Never invent answers.**
4. **Create.** Run `sdlc new <kebab-slug> --title "<Title>"`, then `git switch -c feat/NNNN-<slug>` (the branch makes the intent active). Delegate the writing to the **product-analyst** subagent with the interview answers.
5. **Validate.** Run `sdlc validate NNNN` and fix every error.
6. **Stop at the gate.** Show a short summary of the intent and its open questions, then say exactly:
   > Review `.aiops/NNNN-slug/intent.md`. Reply with corrections, or type **`Intent Approved NNNN`** to move to SPECIFICATION.

   **Don't continue until the approval context appears.** If the human asks for changes, edit and validate again.

| Red flag | Do instead |
|---|---|
| Starting the spec "to save time" | The spec is blocked until the gate opens. Wait. |
| Filling an unknown with a plausible guess | Add it to Open questions with who can answer. |
