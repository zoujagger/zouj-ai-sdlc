# Install and configure

The short version is in the [README](../README.md#install). This page has the details: the setup command, the
install paths, the scaffold parts, the profiles and the per-repo configuration.

Requirements: `git`, `make`, `python3` ≥ 3.9 (stdlib only), Claude Code ≥ 2.1. `gh` and `jq` are optional. Check your
installed release with `/plugin list`.

> **Official sources only:** the repository `github.com/zoujagger/zouj-ai-sdlc` and the marketplace/plugin id
> `zouj-ai-sdlc@zouj`. Copies elsewhere aren't reviewed.
>
> **What you trust:** enabling the plugin trusts github.com/zoujagger/zouj-ai-sdlc at that ref. Its hooks run as you on
> every tool call, and `bin/sdlc` is what you run to approve. So the commands and the snippet pin a release tag (`ref`),
> and moving to a new release should be a reviewed change: rerunning `sdlc setup` after an upgrade proposes it as a
> diff.

## The typed setup command
**You set the profile, by typing it.** Typed as your whole prompt, `/zouj-ai-sdlc:setup solo` (or `team`, or
`strict`) writes the core scaffold into a repo that has none (missing files only: nothing you have is changed), sets
the repo's first profile, and commits `.aiops/config.json` alone. The reply lists every file it created and the steps
only you can do (signing, CODEOWNERS, committing the rest).

Claude can't do this for you: a tool call can't author a prompt, and setup run by Claude never changes that file. It
works once per repo, while the config is untouched and nothing is approved
([ADR 0003](adr/0003-first-profile-by-typed-setup-command.md)).

Want to look first? Type `/zouj-ai-sdlc:setup` alone: it checks the prerequisites, previews every change and the
gates, then asks you to type the command. Changing a profile later is a run in your own terminal:
`sdlc setup --profile solo|team|strict [--dry-run] [--yes]`.

## In your own terminal
Inside Claude Code, `sdlc` is on PATH. In your own terminal it isn't, and a few commands are yours alone:
- `setup --profile` on a repo that has a profile;
- `approve`, `close`, `unlock`;
- `uninstall`.

Run `sdlc where` in Claude Code (or ask Claude to). Its first line is the command to paste, with the absolute paths,
for example `/usr/bin/python3 -I ~/.claude/plugins/cache/zouj/zouj-ai-sdlc/<version>/bin/sdlc`. That is what
`<plugin>/bin/sdlc` stands for in these docs. When a human step is pending, `sdlc status` and the session card show
the same line as `Your terminal:`.

## Core by default, the rest opt-in
Setup and `init` install the core scaffold:
- `.aiops/`, CLAUDE.md, REVIEW.md;
- the Makefile contract. A `setup` or `init` you run yourself wires it from the detected stack: `--stack auto` is
  the default, `--stack <name>` forces one, and `--stack none` keeps the stubs. Run by Claude, or as the typed
  setup command, they only list the commands and the terminal command that wires them. A Makefile you've edited
  is never changed;
- the project settings, CODEOWNERS and the PR template;
- the two workflows the gates need (`aiops-gates.yml`, `ci.yml`).

Nothing in it runs on a schedule or needs a secret. Add the rest by part, now or later, with
`sdlc setup --with <part>[,<part>…]` (or `--with all`):

| Part | Adds | Needs |
|---|---|---|
| `review` | Claude reviews pull requests and answers `@claude` mentions | `ANTHROPIC_API_KEY` (or the Claude GitHub App) |
| `maintain` | control bands (`ops/bands.yaml`), the Maintain and weekly scan workflows, runbook, postmortem and retro folders | the secret, and real metric queries |
| `deploy` | the deploy workflow and release notes | `make deploy` wired, GitHub Environments |
| `governance` | policy examples, branch-protection notes, the ADR folder, Dependabot | nothing |
| `issues` | issue forms and automated triage | the secret, for triage |

`--with` only adds. A rerun without it keeps the parts you have, and the setup preview names the ones left out.

## Other install paths
**Just the plugin.** The two `/plugin` commands from the README, then, in each repo:
1. `/zouj-ai-sdlc:init` (or `sdlc init [--stack auto|none|python|node|go|java|react|angular] [--with <parts>]`);
2. type `/zouj-ai-sdlc:setup <profile>`.

**For a team, declaratively.** Commit the snippet from the README to the project's `.claude/settings.json`. `init`
and `setup` write it for you. Claude Code then offers the plugin to everyone who opens the repo.

## Profiles
Profiles change only how a human approval is proven. The workflow and every gate are the same:

| Profile | Approval proof | For |
|---|---|---|
| `solo` | the typed phrase + an unsigned approval commit | one developer, trying it out |
| `team` | an SSH-signed commit, a human per signature (passphrase key out of ssh-agent) | most teams |
| `strict` | an `sk-` key touch per signature, plus CODEOWNERS on `/.aiops/` | regulated or high-risk repos |

`team` and `strict` need a signing key: see [approver setup](approver-setup.md). Not sure how far to go? The
[adoption ladder](adoption.md) goes one step at a time, from the plugin alone to `strict` with the Maintain loop.

Without `.aiops/`, the plugin's **SDLC gates are dormant** until you run setup or init. Its safety guards are on in
every repo:
- secret reads;
- force-push and history rewrites;
- production deploys;
- writes (Edit/Write and shell) to secrets outside the repo, your shell startup files, PATH, global git config and
  the installed plugin.

## Configuration
Per repo, human-owned:
- **`.aiops/config.json`:**
  - `profile`: set once by the typed `/zouj-ai-sdlc:setup <profile>`, changed by `sdlc setup --profile` in your
    terminal;
  - `lock_when_idle` (default true);
  - `commit_approvals`;
  - `main_branch`;
  - `require_signed_approvals` (default **true**).
- **`.aiops/config/allowed-signers`** (keys allowed to approve) and **`legacy-approvals`** (pre-signing approvals the
  audit still accepts).
- **`.aiops/config/{readonly-exempt,protected-paths,secret-paths,test-paths}`** extend the plugin's `defaults/`.
- **`SDLC_HOOK_PROFILE=spike`** lifts the read-only lock and `make check` for throwaway exploration. The approval and
  merge gates still hold.
- **The active intent** comes from the branch (`feat/NNNN-*`), else `sdlc use NNNN`, else `$AIOPS_INTENT`.
- **Unattended state 4:** plugins can't grant permissions. Either:
  - start the session in auto mode (`claude --permission-mode auto`; a user setting, which Claude Code ignores in
    project settings), or
  - add the allow-rules from `.aiops/README.md` to `.claude/settings.json`.

  The guards run either way.
