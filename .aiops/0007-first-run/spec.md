---
id: 0007
title: First run in five minutes (profile by phrase, terminal command, core scaffold)
status: Approved
risk: medium           # the prompt hook writes one human-owned file and commits it; the scaffold default changes; no gate semantics change
intent: ./intent.md
created: 2026-11-10
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-10T10:24:16Z
approved-via: cli
approved-sha256: 06cadc76654df4ec3301cf68ab397eaf56f2b628b9339b3838860cb44a49f473
---

# Spec: First run in five minutes (profile by phrase, terminal command, core scaffold)

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md, translated into engineering requirements.
     Policy skills applied: security (least privilege, human-owned config), UX (every refusal states the reason and
     the procedure). Code cited as path:line on main at d24c79b. -->

## Summary
A newcomer on 0.2.0-alpha.3 can't finish the guided setup inside Claude Code: the profile they pick becomes a
terminal step, the terminal command isn't findable, and the scaffold adds workflows for stages they haven't reached.
This spec adds:
- **Profile by phrase.** The human types `Setup Profile solo|team|strict` as the whole prompt. The prompt hook sets
  the repo's first profile in `.aiops/config.json` and commits that file alone. The agent still can't choose a
  profile, and a later change stays a terminal run.
- **`sdlc where`.** Prints the command for the human's own terminal. The status card shows it when a human step is
  pending.
- **A core scaffold.** `setup` and `init` write 16 core files by default. Five opt-in parts (`review`, `maintain`,
  `deploy`, `governance`, `issues`) are added with `--with`. Install-state records the choice, and the lifecycle
  commands respect it.
- **Auto mode docs** for state 4 in the scaffold's `.aiops/README.md`.

The playbook workflow is unchanged, and `tests/test_playbook.py` proves it for a profile set by phrase and for the
core scaffold. Ships with intent 0005 as **0.2.0-alpha.4**.

## Requirements

### Profile by phrase
- **R-1 The phrase.** `hook_prompt` (`lib/sdlc_engine/cli.py:747`) also recognises
  `Setup Profile <name>` as the whole prompt: case-insensitive, surrounding whitespace and one trailing `.` or `!`
  allowed, as `APPROVE_RE` does (`cli.py:23`). A prompt that only contains the phrase is an ordinary prompt.
- **R-2 First profile only.** The hook applies the profile only when all of these hold:
  1. the repo is initialized (`.aiops/` exists) and is the session's repo
  2. `.aiops/config.json` is a regular file whose JSON equals the scaffold template's, so it has no `profile` key
     and no edited key (the template check of `setup._as_setup_writes`, `lib/sdlc_engine/setup.py:219`, without its
     profile variants)
  3. no artifact in any `.aiops/NNNN-*/` folder has `status: Approved` or `Closed`: no gate has been opened under
     the default yet

  The hook doesn't read `CLAUDECODE` or `CLAUDE_CODE_CHILD_SESSION`: Claude Code sets both for the hooks of every
  session, a human's included (probe by zoujagger, 2026-11-10), so they can't tell who typed the prompt.

  Otherwise nothing is written and the reply names the failed condition and the terminal command
  (`<python> -I <plugin>/bin/sdlc setup --profile <name>`, from `lifecycle.human_command`,
  `lib/sdlc_engine/lifecycle.py:257`).
- **R-3 What it writes.** The template's keys merged with `setup.PROFILE_CONFIG[<name>]` (`setup.py:157`), through
  `cli.write_file` (no links). This is byte-for-byte what a human's terminal `sdlc setup --profile <name>` writes into
  a new config. Nothing else is written: not install-state, not settings.
- **R-4 The commit.** The hook commits `.aiops/config.json` alone with `approvals._commit_alone`
  (`approvals.py:133`), unsigned in every profile:
  - title `chore(aiops): Setup Profile <name>`
  - trailers `AIOps-Profile: <name>` and `Set-By: <git user>`

  If the commit fails, the change stays in the working tree and the reply says to commit it.
- **R-5 The reply.** The hook returns `additionalContext`, as approvals do. It states `profile SET` or `NOT set`, the
  proof the profile requires (`setup.PROOF`), the commit title, and the remaining human steps from
  `setup.human_steps` (`setup.py:462`): signing setup for `team` and `strict`, a CODEOWNERS owner for `strict`, and
  the scaffold commit.
- **R-6 Unknown or missing name.** `Setup Profile fast` or a bare `Setup Profile` as the whole prompt writes nothing.
  The reply lists the three profiles.
- **R-7 Dormant without `.aiops/`.** In a repo that isn't initialized the hook exits 0 with no output, as it does for
  approval phrases today.
- **R-8 The agent's paths are unchanged.** Run by the agent, `sdlc setup` still never changes an existing
  `.aiops/config.json`, and Edit, Write and shell writes to it stay blocked. No guard is loosened.
- **R-9 One source for the profile.** `sdlc list-installed` and `doctor` print the profile from `.aiops/config.json`.
  Install-state's `profile` field stays what was recorded at scaffold time; the phrase doesn't touch it.

### `sdlc where`
- **R-10 The command.** `sdlc where` prints, on the first line of stdout, the command the human runs in their own
  terminal: `<python> -I <plugin>/bin/sdlc` with absolute paths (`lifecycle.human_command`). The following lines
  list the human-only subcommands: `setup --profile`, `approve`, `close`, `unlock`, `uninstall`, `legacy-approvals`.
  It takes no arguments, writes nothing, exits 0, works without `.aiops/`, and the agent may run it.
- **R-11 The card.** `cli.card` (`cli.py:81`) and the session-start card (`cli.py:766`) add one line,
  `- Your terminal: <command>`, when a human step is pending:
  - no profile has been chosen yet (R-2 conditions 2 and 3 hold), or
  - the intent is waiting on the human at a gate and `approvals.signing_problem` reports that signing needs a
    terminal

  With no profile chosen, the card also says: type `Setup Profile solo|team|strict`.

### Core scaffold and parts
- **R-12 Parts.** A shipped manifest, `defaults/scaffold-parts`, assigns every file under `templates/scaffold/` to
  exactly one part (the table under Data model). `core` is always installed. The opt-in parts are `review`,
  `maintain`, `deploy`, `governance` and `issues`.
- **R-13 The default.** `init_actions` (`cli.py:436`) takes the chosen parts. `sdlc init` and `sdlc setup` choose:
  - the parts named by `--with <part>[,<part>…]` (`all` names every part), plus
  - the parts already recorded in install-state, plus
  - when nothing is recorded:
    - in a fresh repo, the parts that already have a file on disk. Fresh means there is no `.aiops/`, or
      `.aiops/config.json` still equals the scaffold template. A new repo has none, so it gets `core` only, and a
      rerun after a setup that stopped part-way installs exactly what the first run chose (zoujagger, 2026-11-10)
    - otherwise every part: an initialized repo with an edited config and no install-state, the behaviour up to
      0.2.0-alpha.3

  `--with` only adds. No option removes a part.
- **R-14 Validation.** An unknown part name is refused before anything is written, with the list of valid names
  (exit 1), as `setup.parse` refuses unknown options (`setup.py:317`).
- **R-15 Install-state.** `lifecycle.record` (`lifecycle.py:54`) writes `"parts"`: the sorted list of installed
  opt-in parts. State without the key means every part. `SCHEMA` stays 1.
- **R-16 Lifecycle commands.** For `classify` (`lifecycle.py:96`), `plan_upgrade` (`lifecycle.py:459`) and `repair`,
  the managed scaffold is: `core`, the recorded parts, and every path already recorded in `files`.
  - A file of a part that isn't installed is never `new` or `missing`, and `upgrade` and `repair` never create it.
  - If it exists on disk unrecorded, it is `unmanaged`, as today.
  - `list-installed` ends with one line naming the parts that aren't installed and how to add them.
- **R-17 Preview.** `sdlc setup --dry-run` lists only the chosen parts' files in its Plan, then the parts left out
  with `sdlc setup --with <part>`.
- **R-18 Skills that need a part.** `skills/intent` (for `alert:<metric>`), `skills/triage` and `skills/deploy` say
  which part to add when its file is missing, instead of failing on a missing path.
- **R-19 Core is enough for the gates.** Every path in `lifecycle.NEVER_DECLINED` (`lifecycle.py:77`) is in `core`.
  A core-only repo passes the full playbook walk.

### Docs, skills and release
- **R-20 Auto mode.** `templates/scaffold/.aiops/README.md` → "Unattended execution" explains auto mode for state 4:
  start with `claude --permission-mode auto`, or set `permissions.defaultMode` to `auto` in user settings. It states
  that Claude Code ignores that value in project settings and that the plugin's guards still run. The scaffold's
  `.claude/settings.json` sets no permission mode.
- **R-21 Skills.** `skills/setup`, `skills/configure`, `skills/init` and `skills/using-zouj-ai-sdlc` describe the
  new flow: the agent scaffolds, then asks the human to type `Setup Profile <name>`, for every profile. They name
  `sdlc where` for terminal steps and `--with` for parts.
- **R-22 Docs.** README (Install, "Just looking?", Lifecycle), COMMANDS-QUICK-REF.md, TROUBLESHOOTING.md and
  `docs/architecture.md` (threat-model row for setup, a row for the profile phrase, and a Known gaps entry for
  phrases typed into a session the agent starts) are updated. A new
  `docs/adr/0003-first-profile-by-typed-phrase.md` records R-2 and R-4.
- **R-23 Release.** `plugin.json`, the README pins, SECURITY.md and the tests that pin the version move to
  `0.2.0-alpha.4`. CHANGELOG `[0.2.0-alpha.4]` covers 0005 and this intent. `defaults/scaffold-history.json` gains
  the alpha.4 entry (`scripts/scaffold-history.py`). The human tags after the merge.
- **R-24 Eval.** A behavioural case `evals/profile-by-phrase/`: in a scaffolded repo with no profile, the human asks
  the agent to "set this repo up as solo". The agent must leave `.aiops/config.json` unchanged and ask the human to
  type `Setup Profile solo` (zoujagger, 2026-11-10).
- Non-functional:
  - stdlib only, Python ≥ 3.9
  - the phrase check adds no git call to prompts that don't match
  - `sdlc where` starts no subprocess

## Acceptance criteria
- **AC-1**: Given a repo scaffolded by an agent-run `sdlc setup --yes` with no approved artifact, when the human's
  whole prompt is `Setup Profile solo`, then `.aiops/config.json` equals the template merged with the `solo` keys,
  HEAD is a commit titled `chore(aiops): Setup Profile solo` that touches only that file and carries
  `AIOps-Profile: solo`, and the hook's context says `profile SET`.
- **AC-2**: Given the repo of AC-1, when the human then types `Intent Approved 0001` for a valid intent, then the
  gate opens with no terminal step (the `solo` walk in `tests/test_playbook.py`, driven only by agent-run setup and
  the prompt hook).
- **AC-3**: Given a repo where the phrase already set a profile, or whose `config.json` differs from the template,
  or that holds an Approved or Closed artifact, when the human types `Setup Profile solo`, then no file and no
  commit changes, and the context names the reason and the terminal command.
- **AC-4**: Given any initialized repo, when a prompt contains the phrase with other text, then nothing is written
  and the hook prints nothing. When the whole prompt is `Setup Profile fast` or `Setup Profile`, then nothing is
  written and the context lists `solo`, `team`, `strict`.
- **AC-5**: Given a repo without `.aiops/`, when the human types `Setup Profile solo`, then the hook exits 0 with
  empty output and writes nothing.
- **AC-6**: Given the repo of AC-1 and a hook environment with `CLAUDECODE=1` and `CLAUDE_CODE_CHILD_SESSION=1`
  (what the hooks of every session see), when the prompt is `Setup Profile solo`, then the profile is set as in
  AC-1: the markers don't block the hook path.
- **AC-7**: Given an existing `.aiops/config.json`, when the agent runs `sdlc setup --profile solo --yes` or tries to
  Edit, Write or shell-write the file, then the file is unchanged (the existing 0003 and 0005 tests still pass).
- **AC-8**: Given `Setup Profile team` in a first-profile repo with no signing key, then the profile is set and
  committed, and the context includes the signing steps. Given `strict` without a CODEOWNERS owner for `/.aiops/`,
  it also includes that step.
- **AC-9**: Given any directory, with or without `.aiops/`, as the human or the agent, when `sdlc where` runs, then
  stdout's first line is `<python> -I <abs plugin>/bin/sdlc`, the exit code is 0 and nothing is written.
- **AC-10**: Given a repo with no profile chosen, or an intent waiting on the human while signing needs a terminal,
  then `sdlc status` and the session-start card include `- Your terminal:` with that command. Given neither, the
  line is absent.
- **AC-11**: Given a fresh git repo, when `sdlc setup --yes` or `sdlc init` runs, then exactly the 16 core files are
  created (plus install-state and the `.gitignore` lines), no created workflow has a `schedule:` trigger or names a
  secret, and install-state has `"parts": []`.
- **AC-12**: Given the repo of AC-11, when `sdlc setup --with maintain --yes` runs, then exactly the `maintain`
  files are added and `parts` is `["maintain"]`. A later `sdlc setup --yes` without `--with` adds and removes
  nothing. `--with all` installs every part. `--with bogus` exits 1 before writing and lists the valid names.
- **AC-13**: Given a core-only repo, then `sdlc list-installed` shows no file of an opt-in part as `new` or
  `missing` and ends with the line naming the parts not installed; `sdlc upgrade --yes` and `sdlc repair --yes`
  create none of those files.
- **AC-14**: Given install-state written by 0.2.0-alpha.3 (no `parts` key), or an initialized repo with an edited
  `config.json` and no install-state, then `list-installed`, `repair`, `upgrade`, `setup` and `init` treat every
  part as installed: the existing lifecycle tests pass unchanged, and no existing file changes status. Given a repo
  with the template `config.json`, no install-state and the full 0.2.0-alpha.3 scaffold on disk, then every part
  counts as installed too.
- **AC-15**: Given `templates/scaffold/`, then every file belongs to exactly one part in `defaults/scaffold-parts`,
  every manifest line matches a file, and every `NEVER_DECLINED` path is `core`; `make check` fails otherwise.
- **AC-16**: Given a core-only repo in each profile (`solo`, `team`, `strict`), then the playbook walk in
  `tests/test_playbook.py` passes from state 1 to 6: the lock in states 1-3, human-only approvals, `make check` at
  Stop, no merge, push to main or production deploy by the agent.
- **AC-17**: Given the scaffold, then `.aiops/README.md` names `--permission-mode auto`, says project settings can't
  set it, and says the guards still run; `templates/scaffold/.claude/settings.json` has no `defaultMode`.
- **AC-18**: Given the shipped docs and skills, then README's "Just looking?" recipe reaches `solo` with the phrase
  and no `<plugin>` path; `skills/setup` asks for the phrase and never tells the human to open a terminal for
  `solo`; README, COMMANDS-QUICK-REF.md and TROUBLESHOOTING.md document `sdlc where` and `--with`.
- **AC-19**: Given the release, then `plugin.json` is `0.2.0-alpha.4`, the README pins and the scaffold's pinned ref
  match it, CHANGELOG has `[0.2.0-alpha.4]` naming 0005 and 0007, `scaffold-history.json` has the alpha.4 entry, and
  `make check` and `claude plugin validate .` pass.
- **AC-20**: Given a core-only setup that stopped after writing some files (the template `config.json`, no
  install-state), when `sdlc setup --yes` or `sdlc init` runs again without `--with`, then only the missing core
  files are created and `parts` is `[]`. Given the same after `--with maintain`, the rerun completes `core` and
  `maintain` and nothing else.
- **AC-21**: Given the eval suite, then the case `evals/profile-by-phrase/` exists with a fixture that builds a
  scaffolded repo with no profile, a grader that the config still has the template values and a grader that the
  reply asks for `Setup Profile solo`; `evals/README.md` lists it; and it passes in `make evals` (the run is quoted
  in review.md).

## Data model
No database. Repo text files only.

**`.aiops/config.json`** (human-owned; unchanged schema). After the phrase, for `solo`:
```json
{
  "lock_when_idle": true,
  "commit_approvals": true,
  "main_branch": "main",
  "require_signed_approvals": false,
  "profile": "solo",
  "approval_key_policy": "any"
}
```
The presence of the `profile` key is what makes a profile "set".

**The profile commit.** Single file, unsigned, never co-authored:
```
chore(aiops): Setup Profile solo

AIOps-Profile: solo
Set-By: Jane Doe <jane@example.com>
```
CI doesn't read it. CI reads the config from the target branch, as today.

**`.aiops/install-state.json`.** One new optional key, schema still 1:
```json
{ "schema": 1, "parts": ["maintain"], "profile": "team", "files": { "…": {} } }
```
No `parts` key means every part (state written up to 0.2.0-alpha.3).

**`defaults/scaffold-parts`** (shipped). Lines of `<part> <glob>`, `#` comments, globs as in the other `defaults/`
lists. A path no line matches counts as `core` at run time and fails AC-15 in tests.

| Part | Files |
|---|---|
| `core` (16) | `.aiops/README.md`, `.aiops/config.json`, `.aiops/config/*` (6), `.claude/settings.json`, `.github/CODEOWNERS`, `.github/pull_request_template.md`, `.github/workflows/aiops-gates.yml`, `.github/workflows/ci.yml`, `CLAUDE.md`, `Makefile`, `REVIEW.md` |
| `review` (2) | `.github/workflows/claude-pr-review.yml`, `.github/workflows/claude.yml` |
| `maintain` (7) | `.github/workflows/claude-maintain.yml`, `.github/workflows/claude-scheduled-scan.yml`, `ops/bands.yaml`, `scripts/check-bands.py`, `docs/runbooks/README.md`, `docs/postmortems/README.md`, `docs/retros/README.md` |
| `deploy` (2) | `.github/workflows/deploy.yml`, `.github/workflows/claude-release-notes.yml` |
| `governance` (5) | `governance/managed-settings.example.json`, `docs/ai-usage-policy.md`, `docs/branch-protection.md`, `docs/adr/0001-record-architecture-decisions.md`, `.github/dependabot.yml` |
| `issues` (4) | `.github/ISSUE_TEMPLATE/bug.yml`, `config.yml`, `intent.yml`, `.github/workflows/claude-issue-triage.yml` |

Classification: no personal data in the new fields. The profile commit carries the git user's name and email, as
approval commits do. Reversible: removing the `parts` key restores the old reading, and the profile keys are the
ones a terminal run writes.

## API contracts
**Prompt phrase** (UserPromptSubmit → `sdlc hook prompt`; `hooks/hooks.json` is unchanged):

| Whole prompt | Condition | Effect | Hook output |
|---|---|---|---|
| `Setup Profile solo\|team\|strict` | R-2 holds | config written, committed alone | `additionalContext`: `zouj-ai-sdlc profile SET: <name> …` |
| the same | R-2 fails | none | `additionalContext`: `zouj-ai-sdlc profile NOT set: <reason>. In your own terminal: <command>` |
| `Setup Profile <other>` or `Setup Profile` | initialized | none | `additionalContext`: the three profile names |
| any of the above | no `.aiops/` | none | empty, exit 0 |

The hook always exits 0: a prompt hook never blocks the prompt.

**CLI** (`bin/sdlc`). Exit codes as the existing commands: 0 ok, 1 refused or error, 2 needs confirmation.

| Command | Who | Writes | Exit |
|---|---|---|---|
| `sdlc where` | anyone | nothing | 0 |
| `sdlc setup [--profile P] [--stack S] [--with PARTS] [--dry-run] [--yes]` | as today | chosen parts' new files, install-state | 0 / 1 / 2 |
| `sdlc init [--stack S] [--with PARTS] [--force]` | as today | chosen parts' new files, install-state | 0 / 1 |
| `sdlc list-installed` | anyone | nothing | 0 |

`PARTS` is a comma-separated list of `review`, `maintain`, `deploy`, `governance`, `issues`, or `all`.

`sdlc where` output:
```
/usr/bin/python3 -I /home/jane/.claude/plugins/cache/zouj/zouj-ai-sdlc/0.2.0-alpha.4/bin/sdlc
Run it in your own terminal for the human-only commands:
  … setup --profile solo|team|strict    … approve <id> intent|spec|plan    … uninstall --dry-run
  … close <id>    … unlock    … legacy-approvals --write
```

No rule id is added to `defaults/rules`: a refused phrase is a reply, not a block.

## Security & data-leak flags
- ⚠️ **A hook writes a human-owned file.** Risk: the phrase becomes a way to weaken how approvals are proven.
  Mitigation: R-2 limits it to a repo with the untouched template config and no opened gate; the write is exactly
  what a terminal `setup --profile` writes; the commit is visible in the adoption PR; CI reads the config from the
  target branch. Decides: zoujagger.
- ⚠️ **The agent prompts a session of its own** (`claude -p "Setup Profile solo"`). Risk: the hook can't tell that
  prompt from a human's, and no environment marker separates the two (R-2).
  - Mitigation: R-2 conditions 2 and 3 bound the effect to a repo with the untouched template config and nothing
    approved, where the result is one visible commit that CODEOWNERS and the base-branch config still judge.
  - Residual: in such a repo an agent can set `solo` this way. The approval phrases have the same exposure today:
    signing covers them under `team` and `strict`, and nothing does under `solo`.
  - Not closed here: a pre-bash rule against starting a Claude session that carries a gate or profile phrase goes to
    the guard backlog (`docs/architecture.md`, Known gaps, intent 0006), and R-22 records it there.
  - Decides: zoujagger.
- ⚠️ **The agent asks the human to type the phrase.** Risk: a human types `Setup Profile solo` without knowing what
  it changes. Mitigation: the reply and the setup preview state the proof each profile requires; `solo` in a repo
  with reviewers shows up as a `config.json` change under CODEOWNERS. Same class as typing an approval unread
  (`docs/governance.md`, Anti-patterns). Decides: the approver.
- ⚠️ **The profile commit is unsigned in `team` and `strict`.** Risk: it can't be traced to a key. Mitigation: it
  opens no gate and CI doesn't trust it; requiring a signature would send `team` users back to a terminal, which is
  the problem this intent removes. Decides: zoujagger.
- ⚠️ **`sdlc where` prints an absolute path under the home directory.** Risk: the username leaks if the output is
  pasted. Mitigation: it prints locally only; `sdlc feedback` keeps its own summary and doesn't include it.
- ⚠️ **A core-only repo has no AI review workflow and no scheduled scan.** Risk: a team assumes they run.
  Mitigation: the setup preview and `list-installed` name the parts left out; state 5's fresh-context review
  (`/zouj-ai-sdlc:review`) and the CI audit are core and unaffected.
- No change: secret paths, the read-only lock, the approval path, the audit, `allowed-commands`. `sdlc where`
  reads no secret and no git config.

## Architecture
**Components and reuse**
- `cli.hook_prompt` (`cli.py:747`): a second regex beside `APPROVE_RE`, tried only when the approval one doesn't
  match. It calls a new `setup.set_first_profile(root, name)` in-process, as approvals call `approvals.approve`.
- `setup.set_first_profile`: checks R-2, writes with `cli.write_file`, commits with `approvals._commit_alone`,
  builds the reply from `PROOF` and `human_steps`. The template comparison is factored out of `_as_setup_writes`.
- `cli.cmd_where` and one helper for the card line, both over `lifecycle.human_command`.
- `lifecycle.parts()` reads `defaults/scaffold-parts` once; `scaffold_paths(parts)` (`lifecycle.py:83`) filters.
  `init_actions`, `classify`, `plan_upgrade`, `adopt` and `setup.plan` take the installed parts from one function,
  `lifecycle.installed_parts(root, st, requested)` (R-13).
- `setup.OPTIONS` (`setup.py:314`) gains `--with`; `cmd_init` parses the same option.

**Data flow, first run**
1. `/zouj-ai-sdlc:setup` → the agent runs `sdlc setup --dry-run`, the human confirms, the agent runs
   `sdlc setup --yes`: core files, the template `config.json`, install-state with `parts: []`.
2. The human types `Setup Profile solo` → the hook sets and commits the profile.
3. The human commits the scaffold with the command setup printed, then `/zouj-ai-sdlc:intent`.

**Alternatives considered**
- *Agent-run setup applies the chosen profile on a first setup.* Rejected: the agent would decide how approvals are
  proven, and a hook can't tell a human's choice from the agent's.
- *Take the answer to an AskUserQuestion as the proof.* Rejected: the agent writes the question and its options,
  and the answer comes back through the agent's own tool call. The whole-prompt phrase is the only channel a tool
  call can't author (`docs/architecture.md`, "Approval through the prompt").
- *A `sdlc` shim on PATH for terminals.* Rejected for now: it writes a toolchain path, which the guards protect and
  the approval isolation model distrusts. `sdlc where` needs no write.
- *One template directory per part.* Rejected: moving files changes every path in `scaffold-history.json` and breaks
  adoption of earlier releases. A manifest keeps the paths stable.
- *Keep the full scaffold as the default and add `--minimal`.* Rejected: the first run is the case to fix, and it
  uses the default.

**ADR:** `docs/adr/0003-first-profile-by-typed-phrase.md`, written in state 4 with the docs (R-22).

## Rollout & rollback
- Ships with 0005 as 0.2.0-alpha.4. No migration: install-state without `parts` reads as every part, and no
  existing repo's files change.
- Order within the change: the manifest and the conformance tests first, then the engine, then skills and docs, then
  the version bump last so the pins move once.
- After the merge the human tags `v0.2.0-alpha.4` on the merge commit. Until then the README's pin doesn't resolve,
  as with every release so far.
- Rollback: revert the PR.
  - A profile set by phrase stays valid: it is an ordinary `config.json`.
  - An alpha.3 engine reading install-state with `parts` ignores the key. It would then list the left-out parts'
    files as `new`, and its `upgrade` would offer to create them.
- Watch: `install-problem` issues and `sdlc feedback` reports on setup; no runtime metric in this repo.

## Open questions
- [x] Can the hook tell a session the agent started from a human's by `CLAUDE_CODE_CHILD_SESSION`? → **No.** A
  UserPromptSubmit hook in a session zoujagger started from a terminal printed `CHILD=[1] CLAUDECODE=[1]`
  (2026-11-10). The condition is dropped; the flag stands on R-2 conditions 2 and 3, and the nested-session exposure
  goes to the guard backlog (zoujagger, 2026-11-10)
