---
name: setup
description: Guided, rerunnable onboarding for zouj-ai-sdlc in the current repo (or a throwaway sandbox). Checks prerequisites, shows what's installed, previews every change with the playbook gates, and applies only after the human confirms. Use when someone asks to install, set up, onboard, reconfigure or try the workflow.
disable-model-invocation: true
---

# Set up zouj-ai-sdlc

Arguments: `$ARGUMENTS` (a profile: `solo`, `team` or `strict`; or `sandbox <dir>`).

The workflow is the AI-Native SDLC Playbook, the **same in every profile**: intent → spec → plan (code read-only) →
TDD execution → fresh-context review → the human merges. Every gate is opened by the human. A profile changes only
how an approval is proven:
- `solo`: the typed phrase and an unsigned approval commit
- `team`: an SSH-signed commit, a human per signature
- `strict`: an `sk-` key touch, plus CODEOWNERS on `.aiops/`

There's no mode without the gates. Never offer one.

1. **Try first?** If the human just wants to see the workflow, run `sdlc setup --sandbox <dir>` (a directory outside
   this repo, e.g. `/tmp/sdlc-sandbox`). Relay the printed walkthrough, and stop.
2. **Ask for the profile** if `$ARGUMENTS` doesn't name one. Use AskUserQuestion with the three profiles above. Most
   solo developers pick `solo` and most teams `team`.
3. **Preview.** Run `sdlc setup --profile <profile> --dry-run`. Show the human:
   - the Preflight rows marked `✗` or `!`, each with its fix
   - the Plan (`+` creates, `~` changes an existing human-owned file)
   - the Gates summary, verbatim

   If any row is `✗`, stop: setup won't write until it's fixed.
4. **Confirm.** Ask the human to confirm the plan in chat. Without a clear yes, stop. Nothing has been written.
5. **Apply.** Run `sdlc setup --profile <profile> --yes`.
   - **Run by you (the agent):** setup creates only new files. It never changes an existing `.aiops/config.json` or
     `.claude/settings.json`; it prints those changes as human steps instead.
   - **Never** write those files yourself, and never write signing keys, `allowed-signers`, CODEOWNERS owners or
     global git config.
6. **Hand over the human steps** exactly as printed, numbered, introduced with "Run these in your own terminal:".
   They include:
   - the `/plugin` commands, or reopening Claude Code in the repo
   - signing setup for `team`/`strict`
   - a real CODEOWNERS owner for `strict`
   - any change to a human-owned file
   - the commit
7. **Doctor.** Relay the `✗` rows of the doctor output that setup printed. Then suggest
   `/zouj-ai-sdlc:intent "<first need>"` once the human has committed the scaffold.

To change the profile later, the human runs `sdlc setup --profile <new>` in their own terminal. Run by the agent,
setup only prints that change.

| Red flag | Do instead |
|---|---|
| "I'll skip the preview to save time" | Always `--dry-run` first; the human confirms the plan. |
| Editing `.aiops/config.json` or `.claude/settings.json` to apply a printed step | Those are human-owned: hand the step to the human. |
| Offering a lighter profile without approvals or the read-only lock | There is none. Suggest the sandbox to try things out. |
