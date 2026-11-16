# ADR 0003: A repo's first profile is set by the typed `/zouj-ai-sdlc:setup <profile>`

- Status: Accepted
- Date: 2026-11-10, amended 2026-11-13 (a separate profile phrase replaced by the typed setup command)
- Deciders: zoujagger (intent 0007 spec gate, and its re-approval after the PR #18 review)

## Context
A profile (`solo`, `team`, `strict`) decides how a human approval is proven, so `.aiops/config.json` is human-owned:
setup run by the agent never changes it, and Edit, Write and shell writes to it are blocked. Up to 0.2.0-alpha.3 that
left one way to choose a profile: the human ran `<python> -I <plugin>/bin/sdlc setup --profile <name>` in their own
terminal. A first-run review showed the cost. The "Just looking?" recipe needed the plugin's cache path before the
first intent, and a solo developer who skipped the step stayed on the `team` default and met the signing ceremony at
the first gate.

Gates already have a human-only channel inside the session: a prompt typed by the human. A tool call can't author a
user prompt, so the `UserPromptSubmit` hook is the cleanest proof of human intent a session offers
(`docs/architecture.md`, Design choices). Claude Code hands that hook a typed skill command as typed
(`/zouj-ai-sdlc:setup solo`), before the skill expands.

One fact limits that proof. Claude Code sets `CLAUDECODE` and `CLAUDE_CODE_CHILD_SESSION` for the hooks of every
session, a human's included (probed by zoujagger on 2026-11-10). The hook therefore can't tell a human's prompt from
the prompt of a session the agent started (`claude -p "…"`).

## Decision
The prompt hook recognises the whole prompt `/zouj-ai-sdlc:setup <name>` (the qualified command only; the name in
any case) and sets the repo's **first** profile. A bare `/setup <name>`, the command with other text, and any other
phrase set nothing. The first draft of this decision used a separate profile phrase; it was removed on 2026-11-13
so that the skill the human already types is the one way in.

**First profile only (spec R-2).** The hook acts only when all of these hold:
1. The prompt's working directory resolves to the session's repo (`CLAUDE_PROJECT_DIR`); unknown, it refuses.
2. `.aiops/config.json` is a regular file whose JSON equals the scaffold template (no `profile` key, no edited key),
   or there is no `.aiops/` at all.
3. No artifact in any `.aiops/NNNN-*/` folder is `Approved` or `Closed`, and no commit on any ref carries an
   `AIOps-Approval:` trailer: no gate has been opened under the default. The history check came from the 0007
   review: the agent may set an artifact back to `Draft`, so the files alone can't prove it.

Otherwise nothing is written, and the reply names the failed condition and the terminal command. The hook reads no
environment marker on this path, because none carries information.

**A fresh repo (spec R-2a).** With no `.aiops/`, the hook first writes the core scaffold, as a human's terminal
`sdlc setup --profile <name> --yes` would: only at the top of the session's git work tree, only where setup's
Preflight passes, and **only missing files**. No existing file changes; a human-owned difference becomes a step in
the reply. Everything but the config stays uncommitted for review. This is the one exception to "gate hooks stay
dormant without `.aiops/`": `hooks/engine.sh` matches this exact prompt on the raw payload before python starts, and
every other prompt in such a repo exits at once.

**What it writes to the config.** The template's keys merged with that profile's keys: byte for byte what a terminal
`sdlc setup --profile <name>` writes into a new config, `team` included.

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
- A fresh repo reaches `solo` with one typed command and no terminal step. A bare `/zouj-ai-sdlc:setup` previews
  the plan first and then asks for the command.
- The skill reads the hook's reminder: `profile SET` (relay the steps), `profile NOT set` (relay the reason), or none
  (preview, then ask). The agent never types the command and never runs `sdlc setup --yes` to set a profile.
- The choice is one small commit in the adoption PR. CI reads the config from the base branch, so on a repo that
  already has a config on its main branch, a profile set on a feature branch changes nothing until a reviewed PR
  merges it.
- **Accepted gap:** an agent that starts its own session can type `/zouj-ai-sdlc:setup solo`; removing the phrase
  doesn't change that. Conditions 1 to 3 bound the effect to the session's repo with the untouched template config
  (or none) and nothing approved, in its files or its history, where the result is a visible commit. The approval
  phrases have the same exposure: signing covers them under `team` and `strict`, and nothing does under `solo`. A
  pre-bash rule against starting a Claude session that carries a gate phrase or the setup command is on the guard
  backlog (`docs/architecture.md`, Known gaps).
- The command is a reply, not a block: no rule id is added to `defaults/rules`.

## Alternatives considered
- *A separate profile phrase, typed as the whole prompt.* Shipped on the 0007 branch and reviewed in PR #18, then
  removed: one way to set a profile, through the skill the human already types.
- *Type the command twice in a fresh repo* (the first run scaffolds, the second sets the profile). Rejected: two
  prompts for one decision.
- *Also accept a bare `/setup <name>`.* Rejected: another plugin's or the user's own `setup` skill could be the one
  that runs, while this hook still sets the profile.
- *Setup run by the agent applies the chosen profile.* Rejected: the agent would decide how approvals are proven, and
  a hook can't tell a human's choice from the agent's.
- *The answer to an AskUserQuestion as the proof.* Rejected: the agent writes the question and its options, and the
  answer comes back through the agent's own tool call.
- *Refuse nested sessions by `CLAUDE_CODE_CHILD_SESSION`.* Dropped: a human's own session sets it too.
- *Let the command change a set profile.* Rejected: a later change, a downgrade included, stays a terminal run
  (intent 0007, open question 1).
- *A `sdlc` shim on PATH for terminals.* Rejected for now: it writes a toolchain path, which the guards protect.
  `sdlc where` needs no write.
