---
name: configure
description: Shows how zouj-ai-sdlc is set up in this repo (profile, key policy, installed files) and previews a profile change with the same safe flow as setup, then hands the human the one terminal command that applies it. Use when someone asks to reconfigure, change the profile or key policy, or check what the plugin installed.
argument-hint: "[solo|team|strict]"
disable-model-invocation: true
---

# Reconfigure zouj-ai-sdlc

Arguments: `$ARGUMENTS` (the profile the human wants: `solo`, `team` or `strict`).

A profile changes only **how** a human approval is proven, never whether a gate exists or who decides:
- `solo`: the typed phrase and an unsigned approval commit
- `team`: an SSH-signed commit, a human per signature
- `strict`: an `sk-` key touch, plus CODEOWNERS on `.aiops/`

The profile and key policy live in `.aiops/config.json`, which is human-owned. This skill only reads and previews.
The human applies the change in their own terminal.

1. **Where things stand.** Run `sdlc list-installed` and `sdlc doctor`. Show the human:
   - the profile and key policy, from doctor's `profile:` row
   - any `✗` doctor row, with its fix
   - any installed file that is `missing`, `stale` or `modified`. Say that `sdlc repair` restores missing files and
     `sdlc upgrade` brings stale ones to this plugin version. Don't run either here.
2. **Pick the profile.** If `$ARGUMENTS` doesn't name one, ask with AskUserQuestion, offering the three profiles
   above. If the human picks the current one, say so and stop.
3. **Preview.** Run `sdlc setup --profile <profile> --dry-run`. Relay the Plan, the human steps it prints (signing
   setup for `team` and `strict`, a real CODEOWNERS owner for `strict`) and the Gates summary, verbatim. Nothing is
   written.
4. **Hand over.** Give the human the command to run in their own terminal, exactly:

   `<python> -I <plugin>/bin/sdlc setup --profile <profile>`

   Use the absolute python and plugin paths from the preview's human steps. Then ask them to commit
   `.aiops/config.json` and anything else it changed, through a reviewed PR. CI reads the config from the target
   branch.

| Red flag | Do instead |
|---|---|
| "I'll just edit `.aiops/config.json`" | It's human-owned, and a guard blocks you. Hand over the command. |
| Running setup without `--dry-run` to save a step | The human applies the change, in their own terminal. |
| Offering a profile without approvals, or `approval_key_policy: "any"` as a shortcut | There's no gateless profile. `"any"` is the human's own escape hatch (README), never a suggestion. |
