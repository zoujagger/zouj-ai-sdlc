---
id: 0004
title: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)
status: Approved
owner: zoujagger
initiator: zoujagger
source: docs/roadmap.md (Phase 2, approved 2026-11-03); clarification interview with zoujagger, 2026-11-06
created: 2026-11-06
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-06T08:06:40Z
approved-via: cli
approved-sha256: ddd9dcfdb63aea919274df300002b818f52d90737168c7b93baadd840df0f66b
---

# Intent: Safe lifecycle: install state, upgrade, rule ids (roadmap phase 2)

<!-- State 1 BRAINSTORMING. Written from the approved roadmap (docs/roadmap.md, Phase 2) and a 4-question interview
     with zoujagger on 2026-11-06. Unknowns go in Open questions, never invented. -->

## Problem
After 0.2.0-alpha.2 a repo can be set up in one command, but nothing after that day-one install is managed:
- **No record of what the plugin installed.** `init` and `setup` write the scaffold, but the repo doesn't record which
  files the plugin owns, which plugin version wrote them, the profile, or the `ZOUJ_SDLC_REF` pin. `init` skips
  existing files without saying whether they are stale, edited or current.
- **No upgrade path.** When the plugin moves to a new version, a repo initialized by 0.2.0-alpha.1 or alpha.2 keeps
  its old scaffold and its old `ZOUJ_SDLC_REF` (a mutable tag, flagged as a residual risk in the threat model).
  Migrations such as `legacy-approvals` are run by hand.
- **No repair or uninstall.** A deleted or damaged scaffold file can only be fixed with `init --force`, which is
  all-or-nothing. There is no safe way to remove the plugin's files from a repo, and no guarantee that a removal
  would spare the `.aiops/NNNN-*` artifacts (the audit trail).
- **Blocks can't be explained or worked around safely.** Guard messages carry no stable id, so a user can't look up
  why a command was blocked or report it precisely. False positives (the main source of frustration in 0001-0003)
  have no outlet except weakening the guards. The only runtime control is `SDLC_HOOK_PROFILE=spike`.
- **Changing the profile, scope or key policy means rerunning `sdlc setup` by hand.** There is no in-plugin entry
  point.

ECC solves these with install-state that records only the files it owns, `list-installed | doctor | repair |
uninstall --dry-run`, stable hook ids, and an in-plugin `configure` command (`docs/roadmap.md`).

## Desired outcome
- **The repo knows what the plugin installed.** `.aiops/install-state.json` records the plugin version, the profile,
  `ZOUJ_SDLC_REF` and a hash of every scaffold file `init`/`setup` wrote. `sdlc list-installed` shows each managed
  file as current, modified by the user, or missing.
- **Upgrading is one command and safe.** After the human updates the plugin with `/plugin`, `sdlc upgrade` brings the
  repo to the **running plugin's** version: it shows a diff of the scaffold, never touches a file the user modified,
  bumps `ZOUJ_SDLC_REF` to a full commit sha, and runs the version's migrations (such as `legacy-approvals`).
- **Repos from 0.2.0-alpha.1 and alpha.2 are adopted, not re-initialized.** The first `upgrade` or `repair` records
  the files that still match a known scaffold version as managed, and lists the ones that differ as user-modified,
  which it never touches (zoujagger, 2026-11-06).
- **Repair restores only what is missing or unmodified-but-stale**, never a user-modified file.
- **Uninstall is exact and human-only.** `sdlc uninstall --dry-run` (anyone) lists what would be removed. A real
  `sdlc uninstall` is refused under the agent, like `approve` and `close` (zoujagger, 2026-11-06). Both remove only
  the files that install-state records, and **never** `.aiops/NNNN-*` artifacts.
- **Every block has an id and an explanation.** Each guard message carries a stable id (for example `G-ENV-03`), and
  `sdlc why <id>` explains the reason, the playbook stage it protects, and the safe alternative.
- **False positives have a safe outlet that can't touch a gate.** A human-owned exact-command allowance,
  `.aiops/config/allowed-commands` (under CODEOWNERS), lets a specific command through a non-gate rule. An
  allowance for any rule that protects a playbook gate is refused: engine calls, approval trailers, artifacts and
  `.aiops/`, the read-only lock, merge and push-to-main, deploy, the test lock, the Stop hook. There is **no per-rule
  disable switch**.
- **`/zouj-ai-sdlc:configure`** runs the same safe `sdlc setup` flow from inside Claude to change the profile, scope or
  key policy.
- **The AI-Native SDLC Playbook workflow (`docs/sdlc.md`) holds before, during and after every lifecycle command, and
  tests prove it** (the roadmap's non-negotiable list):
  - `upgrade`, `repair` and `uninstall` never open a gate, never remove an artifact or an approval, and never weaken
    the read-only lock, the human gates, the Stop hook, or the merge, push-to-main and deploy guards
  - `tests/test_playbook.py` additionally checks that an `allowed-commands` entry for a gate rule is rejected
  - `init` → `upgrade` → `uninstall --dry-run` round-trips touching only managed files
- Shipped as **0.2.0-alpha.3**.

## Users & systems affected
- **Users:**
  - maintainers of repos initialized by 0.2.0-alpha.1 or alpha.2 who need to upgrade
  - adopters who want to remove or repair the plugin's files
  - developers hit by a false-positive block, and the human owners who approve an allowance
  - approvers changing their profile or key policy
- **Systems:**
  - `bin/sdlc` and `lib/sdlc_engine/` (install-state, the new commands, `why`, the allowance check, migrations;
    building on `init_actions`/`apply_init`, `cmd_init`, `cmd_setup`, `cmd_doctor`, `cmd_legacy_approvals`)
  - `hooks/` (stable ids in every block message, the `allowed-commands` lookup) and `lib/sdlc_engine/guards.py`
  - `templates/scaffold/` (CODEOWNERS for install-state and `allowed-commands`, `ZOUJ_SDLC_REF`)
  - `skills/` (a new `configure` skill; `setup` and `status` mention the lifecycle commands)
  - README, `COMMANDS-QUICK-REF.md`, `TROUBLESHOOTING.md`, `docs/architecture.md` (threat model), CHANGELOG
  - `tests/` (`test_cli.py` following `Init::test_scaffold_pins_and_protects`, `test_playbook.py`, guard tests)

## Constraints
- **The playbook workflow is non-negotiable** (`docs/roadmap.md`). No lifecycle command, allowance or profile may
  change whether a gate exists or who decides. There is no gateless, advisory or per-rule-disable mode.
- **Stdlib-only Python ≥ 3.9**, no new runtime dependencies; `make`, `gh` and `jq` stay (standing decision).
- **Upgrade takes its target from the running plugin.** It does no network fetch of its own; the human updates the
  plugin with `/plugin` first (zoujagger, 2026-11-06).
- **`.aiops/install-state.json` is engine-written and guarded** (zoujagger, 2026-11-06): only `sdlc init`, `setup`,
  `upgrade`, `repair` and `uninstall` write it. The agent's Edit/Write and shell writes to it are blocked, and it is
  under CODEOWNERS with `.aiops/config*`.
- **Human-owned files stay human** (as in 0003): under the agent, lifecycle commands never change
  `.aiops/config.json`, `.aiops/config/` (including `allowed-commands`), `.claude/settings.json`, CODEOWNERS or
  `.github/workflows/`; they print the exact change for the human.
- **Writes follow 0003's rules:** only regular files at the top of the git repo the command runs in, never through a
  link, never in `$HOME`, `~/.claude` or a toolchain path; `--dry-run` writes nothing.
- **`sdlc init` still never overwrites an existing file** (CLAUDE.md rule 5). Overwriting is `upgrade`'s and
  `repair`'s job, and only for unmodified managed files.
- **Engine and guards are test-first** (CLAUDE.md rule 2), and every block message states the reason **and** the
  procedure, now with its id.
- **Existing 0.2.0-alpha.1 and alpha.2 repos keep working** without running any new command.

## Out of scope
- Phase 3 (PyPI or `uvx` distribution, macOS and Windows support, a short plugin id, marketplace metadata) and
  Phase 4 (other harnesses), per `docs/roadmap.md`.
- A per-rule disable switch, an advisory mode, or allowances by pattern rather than exact command.
- Changing the gates, the state machine, the approval record or the review personas.
- Upgrading the plugin itself (that stays `/plugin`); `upgrade` only brings a repo's scaffold to the installed plugin.
- Fixing the 0.2.0-alpha.2 known issues unrelated to the lifecycle (the CHANGELOG list); they get their own intent.

## Open questions
- [x] Does a real `uninstall` ship, and who runs it? → **Yes, human-only;** `--dry-run` is open to everyone
  (zoujagger, 2026-11-06)
- [x] How are repos without install-state treated? → **Adopted with a diff:** files matching a known scaffold version
  become managed, the rest are listed as user-modified and never touched (zoujagger, 2026-11-06)
- [x] Where does `upgrade` get the new version? → **The running plugin;** no fetch (zoujagger, 2026-11-06)
- [x] Who owns `install-state.json`? → **The engine, guarded** against agent edits, under CODEOWNERS (zoujagger,
  2026-11-06)
- [ ] Which current guard rules count as "protecting a playbook gate" (no allowance possible), beyond the roadmap's
  list? The spec should enumerate every existing rule with its id and class. (zoujagger, at the spec gate)
- [ ] Should `upgrade` resolve `ZOUJ_SDLC_REF`'s full sha from the running plugin's own git checkout, and what does it
  do when the plugin cache has no `.git` (marketplace install)? (spec, to verify against how Claude Code installs
  plugins)
- [ ] Does `/zouj-ai-sdlc:configure` add anything beyond invoking the `setup` flow (for example a key-policy change
  walkthrough), or is it a thin alias? (zoujagger)
