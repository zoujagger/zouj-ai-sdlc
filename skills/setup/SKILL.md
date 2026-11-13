---
name: setup
description: Guided, rerunnable onboarding for zouj-ai-sdlc in the current repo. Checks prerequisites, shows what's installed, previews every change with the playbook gates, and applies only after the human confirms. Use when someone asks to install, set up, onboard, reconfigure or try the workflow.
disable-model-invocation: true
---

# Set up zouj-ai-sdlc

Arguments: `$ARGUMENTS` (a profile: `solo`, `team` or `strict`).

The workflow is the AI-Native SDLC Playbook, the **same in every profile**: intent → spec → plan (code read-only) →
TDD execution → fresh-context review → the human merges. Every gate is opened by the human. A profile changes only
how an approval is proven:
- `solo`: the typed phrase and an unsigned approval commit
- `team`: an SSH-signed commit, a human per signature
- `strict`: an `sk-` key touch, plus CODEOWNERS on `.aiops/`

There's no mode without the gates. Never offer one.

1. **Try first?** If the human just wants to see the workflow, point them to the README's **Just looking?** recipe:
   they create a throwaway repo themselves and run this skill there. Don't create it for them, and stop.
2. **Ask for the profile** if `$ARGUMENTS` doesn't name one. Use AskUserQuestion with the three profiles above. Most
   solo developers pick `solo` and most teams `team`.
3. **Preview.** Run `sdlc setup --profile <profile> --dry-run`. Show the human:
   - the Preflight rows marked `✗` or `!`, each with its fix
   - the Plan (`+` creates, `~` changes an existing human-owned file, `!` a human-owned file that no commit has and
     that holds something setup doesn't write), and the line naming the opt-in parts it leaves out
   - the "Review before committing" section, verbatim: it shows what those `!` files contain
   - the Gates summary, verbatim

   If any row is `✗`, stop: setup won't write until it's fixed.
4. **Confirm.** Ask the human to confirm the plan in chat. Without a clear yes, stop. Nothing has been written.
5. **Apply.** Run `sdlc setup --profile <profile> --yes`. Run by you (the agent), setup creates only new files:
   the core scaffold, with `.aiops/config.json` at init's defaults and **no profile yet**. It never changes an
   existing `.aiops/config.json` or `.claude/settings.json`; it prints those changes as human steps instead.
6. **The human sets the profile.** Ask them to type `Setup Profile <profile>` as their whole prompt, whichever
   profile they chose, `team` included. Then wait.
   - A system reminder says `profile SET` and lists the remaining human steps. Relay them.
   - If it says `profile NOT set` (a profile is already set, the config was edited, or something is already
     approved), relay the terminal command it gives.
   - **Never** type, quote back as done, or simulate the phrase, and never write `.aiops/config.json`, signing keys,
     `allowed-signers`, CODEOWNERS owners or global git config yourself.
7. **Hand over the human steps** exactly as printed, numbered, introduced with "Run these in your own terminal:".
   They include:
   - signing setup for `team`/`strict`
   - a real CODEOWNERS owner for `strict`
   - any change to a human-owned file
   - the commit
8. **Doctor.** Relay the `✗` rows of the doctor output that setup printed. Then suggest
   `/zouj-ai-sdlc:intent "<first need>"` once the human has committed the scaffold.

**Opt-in parts.** Setup installs the core scaffold: `.aiops/`, CLAUDE.md, REVIEW.md, the Makefile, the project
settings and the two CI workflows the gates need. Add `--with <part>` (comma-separated, or `all`) to steps 3 and 5
only when the human asks for what a part does:
- `review`: Claude reviews pull requests (needs `ANTHROPIC_API_KEY`)
- `maintain`: control bands, scheduled scans, runbook and postmortem folders
- `deploy`: the deploy workflow and release notes
- `governance`: policy examples and dependency updates
- `issues`: issue forms and automated triage

A part can be added later by rerunning setup with `--with`. Nothing removes one.

**Already set up?** `sdlc list-installed` shows what the plugin installed and each file's status. `sdlc repair`
restores missing files, and `sdlc upgrade` brings the scaffold to a newer plugin version (the human updates the
plugin with `/plugin` first). Both keep every file the user modified. `/zouj-ai-sdlc:configure` previews a profile
change.

The phrase sets a repo's **first** profile only. To change it later, the human runs `sdlc setup --profile <new>`
in their own terminal; `sdlc where` prints that command with the plugin's full path. Run by the agent, setup only
prints the change. That "never under the agent" check reads Claude Code's environment markers, so it is a deterrent,
like the other local guards: the guarantee is CI, which reads the config, the signers and CODEOWNERS from the target
branch.

| Red flag | Do instead |
|---|---|
| "I'll skip the preview to save time" | Always `--dry-run` first; the human confirms the plan. |
| Editing `.aiops/config.json` or `.claude/settings.json` to apply a printed step | Those are human-owned: hand the step to the human. |
| "They picked `solo` in my question, so the profile is set" | Only the phrase they type sets it. Ask for it and wait for `profile SET`. |
| Offering a lighter profile without approvals or the read-only lock | There is none. Suggest the README's throwaway-repo recipe to try things out. |
