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

**How the profile is set.** When the human types `/zouj-ai-sdlc:setup <profile>` as their whole prompt, the prompt
hook acts **before this skill runs**. In a repo with no `.aiops/` it writes the core scaffold first (missing files
only, nothing existing changed). Then it sets the first profile and commits `.aiops/config.json` alone. Only that
qualified form counts: a bare `/setup <profile>`, or the command with other text, sets nothing.

1. **Read the hook's reminder first.**
   - It says `profile SET`: relay the files it created, its `Makefile:` block (the detected stack's commands, not
     wired yet: the human reviews them and wires them from their own terminal with the command it gives), and the
     human steps exactly as numbered. Introduce
     terminal commands with "Run these in your own terminal:", and keep steps that happen in Claude Code (such as
     a `git` commit you may run for them only if asked) apart. Write nothing yourself. Go to step 6.
   - It says `profile NOT set`: relay the reason and the terminal command it gives, then stop.
   - There's no reminder: continue with step 2. If `$ARGUMENTS` names a profile anyway, the human typed a bare
     `/setup …` or added text: tell them the exact form, `/zouj-ai-sdlc:setup <profile>`, as the whole prompt.
2. **Try first?** If the human just wants to see the workflow, point them to the README's **Just looking?** recipe:
   they create a throwaway repo themselves and type `/zouj-ai-sdlc:setup solo` there. Don't create it for them, and
   stop.
3. **Ask for the profile.** Use AskUserQuestion with the three profiles above. Most solo developers pick `solo` and
   most teams `team`. Their answer doesn't set anything: it only picks what to preview.
4. **Preview.** Run `sdlc setup --profile <profile> --dry-run`. Show the human:
   - the Preflight rows marked `✗` or `!`, each with its fix
   - the Plan (`+` creates, `~` changes an existing human-owned file, `!` a human-owned file that no commit has and
     that holds something setup doesn't write), and the line naming the opt-in parts it leaves out
   - the "Review before committing" section, verbatim: it shows what those `!` files contain
   - the **Stack** block: the detected stack and each Makefile target's command (`--stack auto`, the default). If
     the human disagrees, preview again with `--stack <name>` (java, node, react, angular, python, go) or
     `--stack none`. Run by you, setup **never wires**: relay the block and the terminal command it names, and say
     that the commands run the repo's own scripts, so the human reviews them before wiring them. A Makefile the
     human has edited is never changed: the block is then only a suggestion
   - the Gates summary, verbatim

   If any row is `✗`, stop: the command would refuse too until it's fixed.
5. **The human types the command.** Ask them to type `/zouj-ai-sdlc:setup <profile>` as their whole prompt,
   whichever profile they chose, `team` included. Then wait for the next turn and start again at step 1.
   - **Never** type, quote back as done, or simulate the command, and never run `sdlc setup --yes` to set a
     profile. Never write `.aiops/config.json`, signing keys, `allowed-signers`, CODEOWNERS owners or global git
     config yourself.
6. **Doctor.** Run `sdlc doctor` and relay its `✗` rows. Then suggest `/zouj-ai-sdlc:intent "<first need>"` once
   the human has committed the scaffold.

**Opt-in parts.** The typed command installs the core scaffold: `.aiops/`, CLAUDE.md, REVIEW.md, the Makefile, the
project settings and the two CI workflows the gates need. Add a part only when the human asks for what it does, by
running `sdlc setup --with <part> --yes` (comma-separated, or `all`), which creates only new files:
- `review`: Claude reviews pull requests (needs `ANTHROPIC_API_KEY`)
- `maintain`: control bands, scheduled scans, runbook and postmortem folders
- `deploy`: the deploy workflow and release notes
- `governance`: policy examples and dependency updates
- `issues`: issue forms and automated triage
- `dsl`: a validated, domain-neutral model of state machines, rules and workflows in `domain/*.dsl.json`, checked by `make validate-dsl`. While it is active, every later spec needs a `## Domain DSL` section, and plans start from the model. `--with all` installs every part but `dsl`: name it (`--with all,dsl`) only when the human asks for domain-first modeling.

Preview it first with `--dry-run`. Nothing removes a part.

**Already set up?** `sdlc list-installed` shows what the plugin installed and each file's status. `sdlc repair`
restores missing files, and `sdlc upgrade` brings the scaffold to a newer plugin version (the human updates the
plugin with `/plugin` first). Both keep every file the user modified. `/zouj-ai-sdlc:configure` previews a profile
change.

The typed command sets a repo's **first** profile only. To change it later, the human runs
`sdlc setup --profile <new>` in their own terminal; `sdlc where` prints that command with the plugin's full path.
Run by the agent, setup only prints the change. That "never under the agent" check reads Claude Code's environment
markers, so it is a deterrent, like the other local guards: the guarantee is CI, which reads the config, the signers
and CODEOWNERS from the target branch.

| Red flag | Do instead |
|---|---|
| "I'll skip the preview to save time" | With no reminder, always `--dry-run` first, then ask for the command. |
| Editing `.aiops/config.json` or `.claude/settings.json` to apply a printed step | Those are human-owned: hand the step to the human. |
| "They picked `solo` in my question, so the profile is set" | Only the command they type sets it. Ask for it and wait for `profile SET`. |
| "I'll run `sdlc setup --profile solo --yes` for them" | Run by you, it never sets a profile. The human types `/zouj-ai-sdlc:setup solo`. |
| Offering a lighter profile without approvals or the read-only lock | There is none. Suggest the README's throwaway-repo recipe to try things out. |
