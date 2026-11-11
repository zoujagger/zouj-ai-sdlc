# ADR 0003: A repo's first profile is set by a typed phrase

- Status: Accepted
- Date: 2026-11-10
- Deciders: zoujagger (intent 0007 spec gate)

## Context
A profile (`solo`, `team`, `strict`) decides how a human approval is proven, so `.aiops/config.json` is human-owned:
setup run by the agent never changes it, and Edit, Write and shell writes to it are blocked. Up to 0.2.0-alpha.3 that
left one way to choose a profile: the human ran `<python> -I <plugin>/bin/sdlc setup --profile <name>` in their own
terminal. A first-run review showed the cost. The "Just looking?" recipe needed the plugin's cache path before the
first intent, and a solo developer who skipped the step stayed on the `team` default and met the signing ceremony at
the first gate.

Gates already have a human-only channel inside the session: a phrase typed as the whole prompt. A tool call can't
author a user prompt, so the `UserPromptSubmit` hook is the cleanest proof of human intent a session offers
(`docs/architecture.md`, Design choices).

One fact limits that proof. Claude Code sets `CLAUDECODE` and `CLAUDE_CODE_CHILD_SESSION` for the hooks of every
session, a human's included (probed by zoujagger on 2026-11-10). The hook therefore can't tell a human's prompt from
the prompt of a session the agent started (`claude -p "…"`).

## Decision
The prompt hook recognises `Setup Profile <name>` as the whole prompt (case-insensitive, one trailing `.` or `!`
allowed, as the approval phrases are) and sets the repo's **first** profile.

**First profile only (spec R-2).** The hook writes only when all of these hold:
1. The repo is initialized (`.aiops/` exists) and is the session's repo.
2. `.aiops/config.json` is a regular file whose JSON equals the scaffold template: no `profile` key, no edited key.
3. No artifact in any `.aiops/NNNN-*/` folder is `Approved` or `Closed`: no gate has been opened under the default.

Otherwise nothing is written, and the reply names the failed condition and the terminal command. The hook reads no
environment marker on this path, because none carries information.

**What it writes.** The template's keys merged with that profile's keys: byte for byte what a terminal
`sdlc setup --profile <name>` writes into a new config. Nothing else: not install-state, not settings.

**The commit (spec R-4).** The hook commits `.aiops/config.json` alone, built with the same plumbing as an approval
commit, and **unsigned in every profile**:
- title `chore(aiops): Setup Profile <name>`
- trailers `AIOps-Profile: <name>` and `Set-By: <git user>`

It is unsigned because it opens no gate and CI doesn't trust it (the audit traces approval commits, and reads the
config from the base branch), and because requiring a signature would send `team` users back to a terminal, which is
what this decision removes. If the commit fails, the change stays in the working tree and the reply says to commit
it.

**Everything else stays human-only in a terminal.** Changing a profile that is set, a downgrade included, is
`sdlc setup --profile <name>` in the human's own terminal, with its diff and confirmation. `sdlc where` prints that
command with the plugin's absolute path. No guard is loosened: the agent's `setup`, Edit, Write and shell writes
still can't change the config.

## Consequences
- `solo` is reachable with no terminal step: the agent scaffolds, the human types one phrase.
- Setup run by the agent asks for the phrase for every profile, `team` included, so the choice is always recorded by
  a commit the human caused.
- The choice is one small commit in the adoption PR. CI reads the config from the base branch, so on a repo that
  already has a config on its main branch, a profile set on a feature branch changes nothing until a reviewed PR
  merges it.
- **Accepted gap:** an agent that starts its own session can type the phrase. Conditions 2 and 3 bound the effect
  to a repo with the untouched template config and nothing approved, where the result is a visible commit. The
  approval phrases have the same exposure: signing covers them under `team` and `strict`, and nothing does under
  `solo`. A pre-bash rule against starting a Claude session that carries a gate or profile phrase is on the guard
  backlog (`docs/architecture.md`, Known gaps).
- The phrase is a reply, not a block: no rule id is added to `defaults/rules`.

## Alternatives considered
- *Setup run by the agent applies the chosen profile.* Rejected: the agent would decide how approvals are proven, and
  a hook can't tell a human's choice from the agent's.
- *The answer to an AskUserQuestion as the proof.* Rejected: the agent writes the question and its options, and the
  answer comes back through the agent's own tool call.
- *Refuse nested sessions by `CLAUDE_CODE_CHILD_SESSION`.* Dropped: a human's own session sets it too.
- *Let the phrase change a set profile.* Rejected: a later change, a downgrade included, stays a terminal run
  (intent 0007, open question 1).
- *A `sdlc` shim on PATH for terminals.* Rejected for now: it writes a toolchain path, which the guards protect.
  `sdlc where` needs no write.
