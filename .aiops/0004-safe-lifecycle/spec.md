---
id: 0004
title: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)
status: Approved
risk: medium           # a deleting command, guard changes and a new allowance path; no gate semantics change
intent: ./intent.md
created: 2026-11-06
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-06T08:16:04Z
approved-via: cli
approved-sha256: ed2eb18cc668a471f656e9ed8fe704c4fabd126c90364dc191166f5487e8aa50
---

# Spec: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)

<!-- State 2 SPECIFICATION. Business goals from the approved intent.md (install-state, upgrade/repair/uninstall,
     stable rule ids with `sdlc why`, a gate-proof exact-command allowance, /zouj-ai-sdlc:configure), translated into
     engineering requirements. Code cited as path:line on main at 0f8d4f6. -->

## Summary
After 0.2.0-alpha.2 a repo can be set up in one command, but nothing manages it afterwards. This spec adds:
- **Install state.** `.aiops/install-state.json` records what the plugin wrote: the version, profile, ref, and a
  hash per scaffold file. It is engine-written and guarded.
- **Lifecycle commands.** `sdlc list-installed`, `repair`, `upgrade` and `uninstall [--dry-run]`. They touch only
  files the plugin manages *and* the user hasn't modified, never `.aiops/NNNN-*`, and never a human-owned file when
  run by the agent.
- **Adoption.** Repos from 0.1.0, 0.2.0-alpha.1 and alpha.2 are adopted by comparing their files with the shipped
  hashes of every released scaffold.
- **Rule ids.** Every block message carries a stable id from one registry, and `sdlc why <id>` explains it.
- **Allowances.** A human-owned exact-command allowance, `.aiops/config/allowed-commands`, can lift one
  *allowable* rule for one exact command. It can never lift a rule that protects a playbook gate, a secret or the
  approval toolchain.
- **`/zouj-ai-sdlc:configure`.** A thin skill over `sdlc setup`.

The playbook workflow is unchanged, and `tests/test_playbook.py` proves it across the new commands. Ships as
**0.2.0-alpha.3**.

## Requirements
- **R-1 Install state.** `sdlc init` and `sdlc setup` (on apply) write `.aiops/install-state.json` (schema under
  Data model). It records:
  - the plugin version and the resolved ref (R-6)
  - the profile and the stack
  - for every scaffold path the plugin manages: the sha256 of the bytes **it wrote** (after the ref substitution and
    stack wiring), and whether the path is human-owned (`HUMAN_OWNED_RE`, `lib/sdlc_engine/cli.py`)

  A file `init` *kept* (it already existed) is recorded only if it matches a known scaffold hash (R-5). Otherwise it
  is listed as `unmanaged` and never touched. Writes go through `write_file` (no links, O_EXCL), like every scaffold
  write.
- **R-2 `sdlc list-installed`.** Read-only, anyone can run it. Prints:
  - the recorded version, profile, ref and stack
  - the running plugin's version
  - each managed path with its status, compared with install-state:
    - `current`: the file matches the recorded hash and the running plugin's template
    - `stale`: the file matches the recorded hash, but the template changed
    - `modified`: the hash differs from the recorded one
    - `missing`
    - `unmanaged`

  Exit 0. With no install-state, it shows what adoption (R-5) would record, and says how to adopt.
- **R-3 `sdlc repair [--dry-run] [--yes]`.**
  - Re-creates `missing` managed files. Never touches `modified` files, and never touches `stale` or `current` ones
    (upgrade does that).
  - Shows the plan and asks once (`--yes` skips the question; with no terminal and no `--yes`, it writes nothing,
    exit 2, as setup does).
  - Under the agent, it skips human-owned paths and prints them as one terminal command for the human.
  - Updates install-state.
- **R-4 `sdlc upgrade [--dry-run] [--yes]`.** Brings the repo to the **running** plugin's version, with no network
  access:
  1. Adopts first (R-5) if there's no install-state.
  2. Plans each managed path:
     - `stale` → replace, showing a unified diff
     - `missing` → create
     - `modified` → keep, and print the diff between the old and new template for the human to merge by hand
     - new template files → create
     - template files removed from the plugin → list (removed only by `uninstall` or by hand)
  3. Sets every `ZOUJ_SDLC_REF` and the marketplace `ref` to the resolved ref (R-6), including in `modified` files,
     where only that one value is rewritten and the rest of the file is kept.
  4. Runs the pending migrations (R-7).
  5. Shows the plan, confirms once, applies, and updates install-state.

  Running it again with nothing changed writes nothing and says "Already at <version>". Under the agent,
  human-owned paths (the workflows, `.claude/settings.json`, `.aiops/config*`, CODEOWNERS) aren't written. They are
  printed as the exact terminal command (`<python> -I <plugin>/bin/sdlc upgrade`) for the human. install-state
  records them as still at the old version, so a later human run finishes the upgrade.
- **R-5 Adoption of uninstalled-state repos.** The plugin ships `defaults/scaffold-history.json`: for each released
  version (0.1.0, 0.2.0-alpha.1, 0.2.0-alpha.2, then every release), the sha256 of every scaffold file **after
  normalizing** the `ZOUJ_SDLC_REF`/`ref` value back to the placeholder. Stack-wired Makefiles count as matching
  when they equal a template with any preset's recipes applied.
  - A file that matches one of these hashes is recorded as managed, at that version.
  - Anything else is `modified` (if the path is a scaffold path) and is never touched.

  Adoption alone writes only install-state. A maintainer script (`scripts/scaffold-history.py`, stdlib) regenerates
  the file from git tags. `make check` fails if the current scaffold's hashes are missing from it.
- **R-6 The ref.** The resolved ref is a full 40-hex commit sha when one is known, otherwise the tag. It is found in
  this order:
  1. The `gitCommitSha` in `~/.claude/plugins/installed_plugins.json`, from the entry whose `installPath` resolves
     to the running plugin root (marketplace installs have no `.git`; this file records the sha, verified on this
     machine).
  2. `git rev-parse HEAD` of the plugin root, when it's a git checkout whose HEAD is reachable from a remote-tracking
     ref (so CI can fetch it).
  3. `v<version>`, with a `!` warning that a tag can move.

  `init` keeps writing `v<version>` (CLAUDE.md rule 5 and the existing test). Only `upgrade` pins the sha.
- **R-7 Migrations.** `lib/sdlc_engine/migrations.py` holds an ordered list. Each migration has:
  - an id
  - `applies(root)` (idempotent detection)
  - `human_only` (bool)
  - `run(root)`, or the terminal command

  `upgrade` lists the pending migrations. Under the agent, a `human_only` migration is printed and never run. The
  first migration is `legacy-approvals`: pending when `approvals.unsigned_approvals(root)` lists commits that aren't
  in `.aiops/config/legacy-approvals`. It is always `human_only` and prints `sdlc legacy-approvals --write`. Applied
  migration ids are recorded in install-state.
- **R-8 `sdlc uninstall [--dry-run] [--yes]`.**
  - `--dry-run`: anyone can run it, and it writes nothing.
  - The real run is **human-only**: refused under the agent (`approvals.running_under_agent()`), exactly like
    `approve`, and blocked by the pre-bash guard.
  - It removes **only** paths that are all three of:
    - recorded in install-state
    - scaffold paths of *some* released version (`scaffold-history.json`), so a tampered install-state can't
      name other files
    - currently equal to their recorded hash
  - `modified` files are kept and listed.
  - It never removes anything under `.aiops/NNNN-*`, `.aiops/state/`, `docs/adr/` other than the scaffold's
    `0001-…`, or anything git-tracked that isn't in the plan.
  - Last, it removes install-state and the `.gitignore` line it added. It leaves `.aiops/` itself and the intent
    folders, so the audit trail stays.
  - It prints the follow-up: commit, and `/plugin uninstall` for the plugin itself.
- **R-9 Rule registry and ids.** `defaults/rules` is a plain-text, bash-greppable table: one line per rule,
  `<id> <class> <stage> <summary…>`.
  - **Ids** look like `G-<AREA>-NN`, with these areas:
    - `BASH`: guard-bash heuristics
    - `ENV`: environment and credential printing
    - `SEC`: secret reads and writes
    - `FILE`: protected paths
    - `TOOL`: approval toolchain and installed plugin
    - `GATE`: human gates and engine calls
    - `LOCK`: read-only lock
    - `ART`: artifacts and `.aiops/`
    - `MERGE`: merge and push to main
    - `DEPLOY`: production
    - `TEST`: test lock
    - `STOP`: Stop hook
    - `SCAF`: scaffold location
    - `FAIL`: fail-closed errors
  - **Classes:** `gate`, `secret`, `toolchain`, `safety`, `heuristic`.
  - **Messages:** every block message in `hooks/*.sh`, `lib/sdlc_engine/guards.py`, `secret_scan.py` and
    `cli.py` starts `BLOCKED [<id>] by <hook>: …`, and still states the reason and the procedure (CLAUDE.md rule 2).
  - Ids are stable: never reused, and retired ids stay in the file marked `retired`.
- **R-10 `sdlc why <id>`.** Prints the rule's summary, its class, the playbook stage it protects (or "safety, every
  repo"), the safe alternative, and whether an allowance is possible. An unknown id exits 1 and lists the near
  matches. Read-only, anyone can run it.
- **R-11 Exact-command allowance.** `.aiops/config/allowed-commands` is human-owned. It is already covered by the
  `.aiops/config*` protection and CODEOWNERS. Each line is `<rule-id> <command…>`, and `#` starts a comment.
  - **When it applies:** when a guard is about to block with id X, and X's class is `heuristic`, and the session's
    exact `tool_input.command` (byte-equal after trimming surrounding whitespace; single-line commands only) is
    listed with id X, then rule X is skipped for that call.
  - **Other rules still apply:** evaluation continues, and every other rule still runs on the same command.
  - **Refused entries:** an entry for a `gate`, `secret`, `toolchain` or `safety` id, an unknown id, or a
    multi-line command is ignored by the hooks. `sdlc doctor` reports it as `✗` with the id's class, and
    `sdlc validate --ci` fails on it (reading the file from `--base`).
  - **No disable switch:** there is no per-rule disable, wildcard or pattern allowance, and no environment
    variable.
- **R-12 Agent guard for the new commands.**
  - The pre-bash guard's scaffold rule (`_scaffold_elsewhere`, `guards.py:380`) extends to
    `upgrade|repair|uninstall`.
  - The human-only rule (`ENGINE_RES`) adds `uninstall` without `--dry-run`.
  - `.aiops/install-state.json` is added to `defaults/protected-paths` (engine-written), so the agent's Edit/Write
    and shell writes are blocked.
  - The scaffold CODEOWNERS gains `/.aiops/install-state.json`.
- **R-13 `/zouj-ai-sdlc:configure`.** A skill that shows the current profile, key policy and install-state
  (`sdlc list-installed`, `sdlc doctor`), runs `sdlc setup --dry-run --profile <choice>`, and then hands the human
  the terminal command, because a profile change edits human-owned `.aiops/config.json`. It's a thin wrapper and
  adds no engine code.
- **R-14 Docs.** README (lifecycle section), `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md` ("blocked: look up the
  id with `sdlc why`; false positive → allowance, if allowed"), `docs/architecture.md` threat model rows for
  install-state, uninstall and allowances, `docs/roadmap.md` Phase 2 status, and the CHANGELOG.
- **Non-functional:**
  - **Performance:** hooks consult the registry and allowances only on the block path, so an allowed call costs
    nothing extra.
  - **Dependencies:** stdlib only, Python ≥ 3.9. The hooks stay bash plus jq or python3, and their regexes stay in
    variables.
  - **Compatibility:** a repo initialized by 0.2.0-alpha.2 keeps working without running any new command.

## Acceptance criteria
- **AC-1**: Given a fresh git repo, when `sdlc init` runs, then `.aiops/install-state.json` exists, lists every
  scaffold path with the sha256 of the bytes written, the version, ref `v<version>`, profile and stack, and is valid
  against the Data model schema.
- **AC-2**: Given an initialized repo where one managed file was edited and one deleted, when `sdlc list-installed`
  runs, then those show `modified` and `missing`, the rest `current`, and nothing is written (tree unchanged).
- **AC-3**: Given AC-2's repo, when `sdlc repair --yes` runs, then the missing file is restored byte-equal to the
  recorded hash, the modified file is unchanged, and install-state is updated.
- **AC-4**: Given a repo at an older recorded version whose template for file A changed and file B was user-edited,
  when `sdlc upgrade --yes` runs as the human, then A is replaced (a diff was printed), B is unchanged except for the
  `ZOUJ_SDLC_REF` line, every ref equals the resolved ref, and install-state records the new version.
- **AC-5**: Given AC-4 run a second time, then it prints "Already at <version>" and writes nothing.
- **AC-6**: Given `upgrade --dry-run` (or no terminal and no `--yes`), then nothing in the work tree changes and the
  full plan is printed (exit 0 for dry-run, 2 for no-terminal).
- **AC-7**: Given `upgrade` run under the agent (`CLAUDECODE=1`), then no human-owned path (`.github/workflows/*`,
  `.claude/settings.json`, `.aiops/config*`, CODEOWNERS) changes, they are printed with the human's terminal
  command, and install-state records them at the old version.
- **AC-8**: Given a repo initialized by 0.2.0-alpha.1 or alpha.2 (built from the tagged/merged scaffold, no
  install-state), when `upgrade` or `repair` runs, then the files equal to a `scaffold-history.json` hash become
  managed, an edited one is `modified` and untouched, and adoption alone writes only install-state.
- **AC-9**: Given `installed_plugins.json` with an entry whose `installPath` is the plugin root, then the resolved ref
  is its `gitCommitSha`; given a git checkout plugin root reachable from a remote ref, then its HEAD sha; otherwise
  `v<version>` with a `!` warning.
- **AC-10**: Given unsigned approval commits not yet in `legacy-approvals`, when `upgrade` runs (human or agent), then
  the `legacy-approvals` migration is listed as pending with its terminal command, is never executed by `upgrade`,
  and is not recorded as applied until `applies()` turns false.
- **AC-11**: Given an initialized repo with intent folders, when `sdlc uninstall --yes` runs as the human, then only
  unmodified managed scaffold paths and install-state are removed; `.aiops/NNNN-*`, `.aiops/state/`, modified files
  and every non-scaffold file remain.
- **AC-12**: Given install-state tampered to list `src/app.py` and `.aiops/0001-x/intent.md`, when `uninstall` runs,
  then neither is removed and both are reported as refused (not a scaffold path / artifact).
- **AC-13**: Given `CLAUDECODE=1`, when `sdlc uninstall` (without `--dry-run`) runs, then it exits 1 with the
  human-only message and removes nothing; `sdlc uninstall --dry-run` succeeds and writes nothing. The pre-bash guard
  blocks the agent's `sdlc uninstall` and allows `sdlc uninstall --dry-run`.
- **AC-14**: Given `init` → `upgrade` → `uninstall --dry-run` in a fresh repo, then the only paths touched (git
  status) across the round trip are managed scaffold paths and install-state.
- **AC-15**: Given the agent's Edit/Write or shell redirect to `.aiops/install-state.json`, then it is blocked with a
  `G-FILE-*` id; the agent's `sdlc upgrade|repair` in another repo (cd, `-C`, `GIT_DIR`) is blocked with `G-SCAF-*`.
- **AC-16**: Given every block site in `hooks/*.sh`, `guards.py`, `secret_scan.py` and `cli.py`, then each emits
  `BLOCKED [<id>]` with an id present in `defaults/rules` and a `Procedure:`; every non-retired id in the registry
  is emitted by at least one site (a test scans the sources and drives each guard).
- **AC-17**: Given `sdlc why G-ENV-03` (or any registered id), then it prints summary, class, protected stage, safe
  alternative and whether an allowance is possible; given an unknown id, exit 1 with near matches.
- **AC-18**: Given a `heuristic` rule that blocks `ls env` and an `allowed-commands` line `<that id> ls env`, then
  `ls env` is allowed, `ls env; git push --force` and `ls  env x` are still blocked, and a different id's block on
  the same command is unaffected.
- **AC-19**: Given an `allowed-commands` entry for any `gate`, `secret`, `toolchain` or `safety` id (for example
  push-to-main, prod deploy, `.aiops/` writes, a secret read), then the command is still blocked, `sdlc doctor`
  shows `✗` naming the class, and `sdlc validate --ci --base <ref>` fails when the base branch's file has it.
- **AC-20**: Given `tests/test_playbook.py` in each profile (`solo`, `team`, `strict`), then the full walk still passes
  and additionally: an `allowed-commands` entry for a gate rule is rejected, and `upgrade`/`repair` run mid-walk
  (states 1-5) leave every gate, the read-only lock and the artifacts unchanged.
- **AC-21**: Given a repo initialized by 0.2.0-alpha.2 with no new command run, then all existing tests and the
  playbook walk pass unchanged (status, gates, hooks).
- **AC-22**: Given `make check`, then it fails if the current scaffold's hashes are missing from
  `defaults/scaffold-history.json` or a `defaults/rules` line is malformed or duplicated.
- **AC-23**: Given `/zouj-ai-sdlc:configure`, then the skill runs only read-only commands and `setup --dry-run`, and
  ends by giving the human the terminal command; `claude plugin validate .` passes.

## Data model
No database. Three new files, all repo text:

**`.aiops/install-state.json`.** Engine-written, committed, protected and under CODEOWNERS:
```json
{
  "schema": 1,
  "plugin_version": "0.2.0-alpha.3",
  "ref": "0f8d4f60aea85ad898969d2dc31dcb351c73404b",
  "profile": "team",
  "stack": null,
  "updated_at": "2026-11-10T09:00:00Z",
  "migrations": ["legacy-approvals"],
  "files": {
    ".github/workflows/aiops-gates.yml": {"sha256": "…", "version": "0.2.0-alpha.3", "human_owned": true},
    "Makefile": {"sha256": "…", "version": "0.2.0-alpha.3", "human_owned": false}
  }
}
```

**`defaults/scaffold-history.json`.** Shipped, generated: `{ "<version>": { "<path>": "<sha256 normalized>" } }`.

**`defaults/rules`.** Shipped: `<id> <class> <stage> <summary…>` lines, plus `# retired` markers. The procedure text
for `sdlc why` lives next to it in `defaults/rules.md`, as a `## <id>` section per rule, so the bash hooks only grep
the one-line table.

**`.aiops/config/allowed-commands`.** Human-owned and not scaffolded by default. The README documents it, and
`sdlc why` prints a ready-to-paste line.

Classification: no personal data. install-state holds paths and hashes only, no usernames or home paths. The ref may
be a public commit sha. The migration is reversible: `uninstall` removes install-state, and deleting
`scaffold-history.json` only disables adoption.

## API contracts
CLI (`bin/sdlc`). Exit codes follow the existing commands: 0 ok, 1 refused or error, 2 needs confirmation or no
terminal.

| Command | Who | Writes | Exit |
|---|---|---|---|
| `sdlc list-installed` | anyone | nothing | 0 |
| `sdlc repair [--dry-run] [--yes]` | anyone; human-owned paths human-only | missing managed files, install-state | 0 / 1 / 2 |
| `sdlc upgrade [--dry-run] [--yes]` | anyone; human-owned paths and `human_only` migrations human-only | stale and new scaffold files, ref values, install-state | 0 / 1 / 2 |
| `sdlc uninstall --dry-run` | anyone | nothing | 0 |
| `sdlc uninstall [--yes]` | **human only** | removes unmodified managed files, install-state | 0 / 1 / 2 |
| `sdlc why <id>` | anyone | nothing | 0 / 1 |

All of them refuse with the existing `scaffold_root_problem` (`cli.py`) rules: top of a git repo, no `GIT_*`
variables, not home, not `~/.claude`, not a toolchain path. Unknown options are refused before anything else, as
setup does (`setup.parse`).

Block message format, in every hook:
```
BLOCKED [G-AREA-NN] by <hook>: <reason>
Procedure: <what to do instead>   (`sdlc why G-AREA-NN` for details)
```
Tests and docs that match the old `BLOCKED by …` prefix are updated in the same commit.

## Security & data-leak flags
- ⚠️ **Uninstall as a deletion primitive.** A tampered install-state could make uninstall remove arbitrary or audit
  files. → Uninstall is human-only (CLI and guard), and it removes a path only if it is recorded **and** a released
  scaffold path **and** unmodified. It never removes `.aiops/NNNN-*` or `.aiops/state`. (AC-11, AC-12, AC-13.) Who
  decides: zoujagger, approved in the intent.
- ⚠️ **Allowances as a gate bypass.** An allowance could lift a gate rule, or a compound command could piggyback on an
  allowed one. → Allowances work only for the `heuristic` class, an exact byte-equal single-line match, one rule per
  entry, with every other rule still evaluated. The file is human-owned under CODEOWNERS, and CI checks it from the
  base branch. (AC-18, AC-19.) **Decision needed:** the class assignment of each existing rule. The proposed
  `heuristic` set is in Open questions. Who decides: zoujagger.
- ⚠️ **Secret reads via allowance.** Allowing a command that reads a secret would bring the secret into the session.
  → The `secret` class is never allowable, and neither are `G-ENV` credential-printing rules. Who decides: zoujagger.
- ⚠️ **Upgrade as a downgrade path for the agent.** The agent's `upgrade` could rewrite workflows (the CI audit),
  `.claude/settings.json` or the config. → Under the agent, human-owned paths are never written (AC-7), and CI
  reads the config and the engine from the base ref anyway. Who decides: covered by the intent constraints.
- ⚠️ **Ref resolution trusts local files.** `installed_plugins.json` and the plugin's git HEAD are writable by
  anything running as the user, so a wrong sha could be pinned. → The sha lands only in human-owned workflow files,
  which only a human's `upgrade` writes, and it's shown in the plan and reviewed in the PR. A sha that doesn't exist
  makes CI fail closed (the fetch fails). Who decides: residual risk, documented in the threat model.
- ⚠️ **install-state leaking local paths.** → It stores repo-relative paths only (AC-1 checks that there are no
  absolute paths). `sdlc feedback` already reduces paths. Who decides: none.
- ⚠️ **Message format change breaks tests or tooling** that grep `BLOCKED by`. → The new prefix still contains
  `BLOCKED` and `by <hook>`, and every message changes in one commit together with its tests. Who decides: none.

## Architecture
- **`lib/sdlc_engine/lifecycle.py` (new).**
  - `load_state` / `save_state`, `classify(root, state)` → statuses, `adopt(root)`, `resolve_ref()`.
  - `plan_repair`, `plan_upgrade` and `plan_uninstall` return actions, as `init_actions` does (`cli.py`), so every
    command previews exactly what it will apply. `apply_*` reuses `write_file`, `symlink_on_path` and
    `scaffold_root_problem` (`cli.py`).
  - `init_actions`/`apply_init` gain a hook that writes install-state, so `init` and `setup` both get R-1 for free
    (setup already applies through `apply_init`, `setup.py:424`).
  - The ref substitution moves into one helper, `render(rel, ref)`, used by `apply_init` and `upgrade`.
- **`lib/sdlc_engine/migrations.py` (new).** The ordered `MIGRATIONS` list. `legacy-approvals` wraps
  `approvals.unsigned_approvals` (used by `cmd_legacy_approvals`, `cli.py:214`).
- **`lib/sdlc_engine/rules.py` (new).**
  - Parses `defaults/rules` and `rules.md`.
  - `why(id)`.
  - `allowed(root, id, command)`, which reads `.aiops/config/allowed-commands` and returns True only for the
    `heuristic` class with an exact match.
  - `allowance_problems(text)`, used by doctor and `validate --ci`.
- **Guards, Python.** `guards._block(rule, …)` (`guards.py:32`) already takes a rule label (`"read-only lock"`,
  `"human gate"`, …). Those labels become ids, so each of its ~40 call sites gets a specific id. `check_bash` asks
  `rules.allowed` before returning a heuristic block, then continues with the next check. `secret_scan.main` and
  the `cli.hook` fail-closed message also get ids.
- **Guards, bash.** `block()` in `guard-bash.sh`, `guard-files.sh`, `guard-read.sh`, `guard-deploy.sh` and
  `guard-tests.sh` takes the id as its first argument. The heuristic checks in `guard-bash.sh` (lines 40-52 today)
  run through a helper, `heuristic <id> <regex-var> …`. On a match, it greps the id's class from
  `$PLUGIN_ROOT/defaults/rules` and the exact command from `$root/.aiops/config/allowed-commands`, comparing them
  as fixed strings, never as a regex or glob. The helper only skips when both match. Allowances apply only in
  initialized repos, since the file lives in `.aiops/`.
- **Doctor and validate.** `cmd_doctor` gets rows for install-state (present / adoptable / stale version) and
  allowed-commands problems. `validate --ci` reads `allowed-commands` from the base ref (as it does for signers) and
  fails on problems.
- **Scaffold.** CODEOWNERS adds `/.aiops/install-state.json`, and `defaults/protected-paths` adds it as
  engine-written. The guard rule `_scaffold_elsewhere` widens `SCAFFOLD_RE`, and `ENGINE_RES` adds
  `uninstall(?!.*--dry-run)`.
- **Skill.** `skills/configure/SKILL.md` is new. `skills/setup` and `skills/status` mention `list-installed`,
  `upgrade` and `why`.
- **Alternatives considered:**
  - Install-state under `.aiops/state/` (gitignored): rejected, because teammates and CI need the same record, and
    upgrade diffs must be reviewable in a PR.
  - Allowance by regex or glob: rejected by the intent (exact only).
  - Upgrade fetching the target from GitHub: rejected by the intent (the running plugin is the target).
  - A JSON registry read by bash: rejected, because a plain line table keeps the block path to `grep -F`, with no
    jq.
- **ADRs:** `docs/adr/` ADR "Allowances can never touch a gate", recording the class model and why there's no
  disable switch.

## Rollout & rollback
- Release **0.2.0-alpha.3** (tag `v0.2.0-alpha.3`). Existing repos change nothing until a human runs `upgrade`
  (AC-21).
- Before generating `scaffold-history.json` for alpha.2, a `v0.2.0-alpha.2` tag must exist (see Open questions).
- **Rollback:** reinstall the alpha.2 plugin with `/plugin`. install-state is ignored by older engines. Deleting
  `.aiops/install-state.json` and `allowed-commands` returns a repo to its alpha.2 shape.
- **Watch:** issues filed with the `install-problem` template that mention upgrade or uninstall, and false-positive
  reports quoting a `G-` id. These ids tell us which heuristics to fix rather than allow.

## Open questions
- [ ] **Rule classes (the decision for this gate).** Proposed: `heuristic`, so allowable, are the guard-bash pattern
  rules with known false positives:
  - `rm -r` of `.`/`*` (`re_rm_root`)
  - `env`/`printenv` as a word (`re_dump_env`, for example `ls env` or `python -m venv env`)
  - `sudo`/`dd if=`/`mkfs`/`chmod -R 777` (`re_system`)
  - curl/wget piped to a shell (`re_pipe_sh`)
  - nested shells too deep to inspect (guards.py `bash`)

  Everything else is not allowable:
  - `gate`: the human gate, read-only lock, artifacts, merge, push to main, deploy, test lock, Stop hook and
    scaffold rules
  - `secret`: secret reads and writes, and credential printing
  - `toolchain`: the plugin, signing config, PATH
  - `safety`: force-push, history rewrite, hook bypass

  Approve as proposed, or move rules between classes. (zoujagger)
- [ ] **Tag `v0.2.0-alpha.2`** doesn't exist locally (only `v0.1.0`, `v0.2.0-alpha.1`). The installed alpha.2 records
  `gitCommitSha` 0f8d4f6 (the PR #9 merge). Should the human tag 0f8d4f6 as `v0.2.0-alpha.2` before the build, so
  `scaffold-history.py` can read every release from tags? (zoujagger)
- [ ] **`/zouj-ai-sdlc:configure`.** Proposed as a thin wrapper (R-13) with no key-policy walkthrough beyond what
  `setup` already prints. OK? (zoujagger)
- [x] Where does `upgrade` get a full sha with no `.git` in the plugin cache? → From `installed_plugins.json`'s
  `gitCommitSha`, verified on this machine (R-6) (spec research, 2026-11-06)
