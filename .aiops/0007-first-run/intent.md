---
id: 0007
title: First run in five minutes (profile by phrase, terminal command, core scaffold)
status: Approved
owner: zoujagger
initiator: zoujagger
source: check against Anthropic's AI-native SDLC playbook and a first-run review (2026-11-10, plan approved by zoujagger); docs/roadmap.md "Next: adoption" (PR #17)
created: 2026-11-10
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-10T10:04:53Z
approved-via: cli
approved-sha256: d74cd8ae1aa6b266474cbecfe9b98dafe31f53b5b7b35b60ea9ccaba307b6102
---

# Intent: First run in five minutes (profile by phrase, terminal command, core scaffold)

<!-- State 1 BRAINSTORMING. Written from the adoption plan zoujagger approved on 2026-11-10, which answered most of the
     interview. Unknowns go in Open questions, never invented. approved-* fields are stamped by the human approval;
     agents never write them. -->

## Problem
A newcomer who follows the guided path in 0.2.0-alpha.3 hits three obstacles before their first approved intent:

- **The guided setup can't deliver the profile they pick.**
  - Run by Claude, `sdlc setup` always writes init's `team` defaults. `solo` or `strict` becomes a human step in
    their own terminal (`skills/setup/SKILL.md` step 5, `setup.apply`).
  - A solo developer who picks `solo` in `/zouj-ai-sdlc:setup` therefore ends up on `team`. Their first
    `Intent Approved 0001` can't succeed until they set up a signing key or find and run the terminal command.
- **The terminal command isn't findable.**
  - `sdlc` is on PATH only inside Claude Code. In a terminal the human needs `<plugin>/bin/sdlc`, and `<plugin>` is
    `~/.claude/plugins/cache/zouj/zouj-ai-sdlc/<version>/`.
  - The engine prints the full command in some refusals (`approvals.approve_command`), but nothing prints it on
    request. `setup --profile`, `approve`, `uninstall`, `legacy-approvals` and `upgrade` of human-owned files all
    depend on it.
- **The scaffold is all-or-nothing.**
  - Setup writes 36 files, 9 of them workflows.
  - Six workflows need `ANTHROPIC_API_KEY`, `claude-maintain.yml` runs every 30 minutes on placeholder metrics, and
    `deploy.yml` runs on every push to main.
  - A first adopter gets failing or noisy workflows for stages they haven't reached.
  - The playbook describes its plays as modular: start with one, then add the next.

A smaller gap: for unattended state 4, `.aiops/README.md` lists allow-rules only. The playbook names auto mode as the
default for routine work once the guardrails are in place, and nothing in the scaffold mentions it.

## Desired outcome
- With the plugin installed, a new user reaches their first approved intent in a fresh repo in about **five minutes**
  under `solo`, **without leaving Claude Code**.
- **The human chooses the profile by typing a phrase as the whole prompt** (`Setup Profile solo|team|strict`), the
  same proof of human intent as an approval. The agent still can't choose, apply or change a profile.
  - The phrase sets a repo's **first** profile only. Changing a profile later, a downgrade included, stays a run in
    the human's own terminal.
  - The hook commits the config change alone, as it does an approval.
- **`sdlc where` prints the exact command for the human's own terminal** (the python and plugin paths in full). The
  session-start card shows it whenever a human step is pending.
- **`setup` and `init` both write a core scaffold by default:** `.aiops/`, CLAUDE.md, REVIEW.md, the Makefile,
  `.claude/settings.json`, `aiops-gates.yml`, `ci.yml`, CODEOWNERS and the PR template. Everything else (PR review,
  Maintain, deploy, governance, the issue templates, `dependabot.yml`, the `docs/` stubs) is opt-in with `--with`, and
  can be added later by rerunning setup. In a default setup, no workflow runs on a schedule or needs a secret.
- `list-installed`, `repair` and `upgrade` respect that choice: a part that wasn't chosen is never reported as
  missing and never created.
- This intent and 0005 ship together as **0.2.0-alpha.4**.
- The scaffold's `.aiops/README.md` explains how to run state 4 in auto mode, with the guards still on.
- **The playbook workflow (`docs/sdlc.md`) still holds, proven by tests,** for every profile, for a profile set by
  phrase, and for both the core and the full scaffold.

## Users & systems affected
- **Users:**
  - new adopters, mostly solo developers trying the workflow for the first time
  - team leads who add the optional parts as their team reaches those stages
  - approvers and maintainers who run human-only commands in a terminal
- **Systems:**
  - `lib/sdlc_engine/cli.py`: the prompt hook, a new `where` command, the session-start card
  - `lib/sdlc_engine/setup.py`: applying a profile, choosing scaffold parts
  - `lib/sdlc_engine/lifecycle.py` and `.aiops/install-state.json`: recording the chosen parts
  - `templates/scaffold/` (`.aiops/README.md`) and `defaults/scaffold-history.json`
  - `skills/setup`, `skills/configure`, `skills/init`, `skills/using-zouj-ai-sdlc`
  - README, COMMANDS-QUICK-REF.md, TROUBLESHOOTING.md, `docs/`
  - `tests/` (`test_setup.py`, `test_cli.py`, `test_lifecycle.py`, `test_playbook.py`) and `evals/`

## Constraints
- **The playbook workflow is non-negotiable** (`docs/roadmap.md`). No gateless mode, and no part of the scaffold that
  a gate depends on may be optional.
- **The agent never chooses a profile.**
  - The phrase counts only as the whole prompt, like an approval phrase, and only in the session's own repo.
  - Where a profile is already set, the phrase changes nothing and the reply gives the terminal command.
  - Agent-run `setup` keeps its current limits on human-owned files.
- **`.aiops/config.json` stays human-owned.** CI keeps reading the config from the target branch, so a profile set
  locally can't open a gate on its own.
- **Existing repos keep working unchanged.**
  - A repo scaffolded with the full set keeps every file after `upgrade` and `repair`.
  - Install-state written by 0.2.0-alpha.3 stays readable.
  - `sdlc init` never overwrites an existing file.
- **Engine rules** (CLAUDE.md):
  - stdlib-only Python ≥ 3.9
  - test-first for `lib/` and `hooks/`
  - every block message states the reason and the procedure
  - SDLC gate hooks stay dormant without `.aiops/`
  - consumer-facing files live in `templates/scaffold/`
- **Auto mode is documentation only.** The plugin never sets a permission mode. Claude Code ignores
  `permissions.defaultMode: auto` in project settings, so the docs point to user settings or `--permission-mode`.

## Out of scope
- macOS and Windows support (intent 0008), one-pass approval for small changes (0009), evals in CI (0010).
- The signing ceremony itself: `team` and `strict` approvals still need the human's key, and a passphrase key still
  needs a terminal.
- A PATH shim or a PyPI package for `sdlc` (roadmap Phase 3).
- The README restructure, the managed-settings example and the REVIEW.md nit cap (the docs pass in the roadmap).
- Changing the gates, the state machine or the review personas.

## Open questions
- [x] May the phrase change an existing profile, including a downgrade (`team` to `solo`)? → **No: it only sets the
  first one.** A later change stays a terminal run (zoujagger, 2026-11-10)
- [x] Does the hook commit the config change, or leave it for the human? → **The hook commits it alone,** as it does
  an approval (zoujagger, 2026-11-10)
- [x] Which files are core? → **`.aiops/`, CLAUDE.md, REVIEW.md, the Makefile, `.claude/settings.json`,
  `aiops-gates.yml`, `ci.yml`, CODEOWNERS and the PR template.** The issue templates, `dependabot.yml` and the `docs/`
  stubs are opt-in; the spec assigns them to parts (zoujagger, 2026-11-10)
- [x] Does `sdlc init` also default to core? → **Yes** (zoujagger, 2026-11-10)
- [x] The release? → **0005 and this intent ship together as 0.2.0-alpha.4** (zoujagger, 2026-11-10)
