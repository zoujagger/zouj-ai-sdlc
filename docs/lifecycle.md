# Lifecycle: upgrade, repair, remove

## Install-state
`init` and `setup` record what they wrote in `.aiops/install-state.json`:
- the plugin version and the CI ref;
- the opt-in parts;
- a hash of every file.

The engine owns that file; the agent can't edit it, and CODEOWNERS covers it. The profile is read from
`.aiops/config.json`, the one place that sets it.

## Commands
| Command | What it does |
|---|---|
| `sdlc list-installed` | Read-only. Lists each installed file's status, then the profile and the parts that aren't installed. Statuses: `current`; `stale` (an older plugin wrote it); `modified` (yours now); `missing`; `unmanaged`; `dropped`; `new`; `declined` (you removed it before adoption: never re-created) |
| `sdlc repair [--dry-run] [--yes]` | Restores missing files. Never touches one you modified |
| `sdlc upgrade [--dry-run] [--yes]` | Run it after you update the plugin with `/plugin`. It replaces stale files (diff shown) and creates new ones. It keeps your modified files, except for the CI ref. It pins every literal `ZOUJ_SDLC_REF` and the zouj marketplace `ref` to the plugin's full commit sha (nothing else, every change shown as a diff first). It lists migrations (e.g. `legacy-approvals`, which only you run) |
| `sdlc uninstall --dry-run`, then `sdlc uninstall` | Removes the plugin's unmodified files, install-state and its `.gitignore` lines. Never `.aiops/NNNN-*`: the audit trail stays. **Human only**: refused inside Claude Code |

## Older repos
Repos set up by 0.2.0-alpha.1 or alpha.2 have no install-state. The first `upgrade` or `repair` adopts them:
- files equal to a released scaffold become managed;
- the rest count as modified and are never touched.

## Limits
- Run by Claude, these commands never write a human-owned file (workflows, `.claude/settings.json`,
  `.aiops/config*`, CODEOWNERS) or code under the read-only lock: they print your terminal command instead.
- A file of a part you didn't install is never `new` or `missing`, and `upgrade` and `repair` never create it.
- Install-state written before 0.2.0-beta.1 names no parts and reads as every part except `dsl`, as before: `upgrade`
  and `repair` never add `dsl`.

## Blocked by mistake?
Every block names its rule (`BLOCKED [G-ENV-03] by guard-bash: …`), and `sdlc why <id>` explains it.

Two heuristic rules accept a human-owned exact-command allowance:
- `G-ENV-03` (env/printenv);
- `G-BASH-07` (sudo and friends).

To allow one, add `<id> <exact command>` to `.aiops/config/allowed-commands`. Never allow a whole-environment dump
such as a bare `printenv`. An allowance lifts that one rule for that one command, and every other rule still runs.

No rule that protects a gate, a secret or the approval toolchain can be allowed, and there is no per-rule disable
switch ([ADR 0002](adr/0002-allowances-never-touch-a-gate.md)).
