---
id: 0003
title: Guided setup and first-run onboarding (roadmap phase 1)
status: Approved
owner: zoujagger
initiator: zoujagger
source: docs/roadmap.md (Phase 1, approved 2026-11-03); comparison with github.com/affaan-m/ECC's install experience
created: 2026-11-03
approved-by: zoujagger <ulrichjagger@gmail.com>
approved-at: 2026-11-03T20:12:07Z
approved-via: cli
approved-sha256: 9c6f43fc25e7c50519743fcf3a5a5f7989a7b7568d3b71c54f9c4a2ad9b812ed
---

# Intent: Guided setup and first-run onboarding (roadmap phase 1)

<!-- State 1 BRAINSTORMING. Written from the approved roadmap (docs/roadmap.md), which answered the interview
     questions. Unknowns go in Open questions, never invented. -->

## Problem
Adopting zouj-ai-sdlc v0.2.0-alpha.1 takes too many manual steps, and a newcomer gets little guidance:
- **Install is three separate steps:** two `/plugin` commands, then `/zouj-ai-sdlc:init` per repo, then signing
  setup. Nothing checks prerequisites first: git, make, python ≥ 3.9, Claude Code, `gh` scopes, a git credential
  helper. Releasing 0.2.0-alpha.1 itself hit a missing credential helper and a missing `workflow` scope.
- **Signing setup is the biggest blocker.** It's 6 commands across 3 files, and doctor only reports problems after
  the fact. The maintainer kept `"approval_key_policy": "any"` rather than go through it.
- **Teammates each install the plugin by hand.** Nothing in a repo offers the plugin to a new contributor.
- **There's no safe way to try it.** `init` turns every gate on in a real repo at once, with no preview of what
  will be enforced.
- **The README explains the state machine, not where to start.** There's no troubleshooting page, command quick
  reference or issue template, and no pinned install commands.

ECC solves the same adoption problems with:
- one pinned, rerunnable, guided setup command with preflight and dry-run
- a declarative `settings.json` marketplace snippet
- a task-first README
- explicit consent before hooks are written
- troubleshooting and feedback surfaces

## Desired outcome
- A new user goes from nothing to their first approved intent in about **10 minutes**, guided by one rerunnable
  command that previews every change before writing it.
- **Profiles** (`solo`, `team`, `strict`) change only how strongly a human approval is proven, never whether a gate
  exists or who decides.
- A contributor who clones an initialized repo is offered the plugin automatically.
- ~~Someone curious can **try** the full intent → … → review cycle in a throwaway sandbox repo before adopting it.~~
  **Deferred to 0.2.0-alpha.3** (zoujagger, 2026-11-04). Three review rounds showed that a sandbox which runs git as
  the human, next to an agent running as the same user, keeps finding new ways into the calling repo. It needs its own
  design.
- The README starts from "what are you doing?" and gives pinned install commands. Troubleshooting, a quick reference
  and issue templates exist.
- **The AI-Native SDLC Playbook workflow (`docs/sdlc.md`) holds in every profile and install path, and that is
  proven by tests:**
  - every stage in order, with its artifact
  - every human gate (intent, spec, plan, merge, production)
  - the read-only lock in states 1-3
  - `make check` green before stop
  - a fresh-context review before the merge

## Users & systems affected
- **Users:**
  - new adopters: solo developers and team leads evaluating the plugin
  - contributors joining an initialized repo
  - approvers who set up signing
- **Systems:**
  - `bin/sdlc` and `lib/sdlc_engine/` (new setup and profile handling, building on `cmd_init` and `cmd_doctor`)
  - `templates/scaffold/` (`.claude/settings.json`, `.aiops/config.json`)
  - `skills/` (a setup or onboarding skill)
  - README and docs, `.github/ISSUE_TEMPLATE/`
  - the tests

## Constraints
- **The playbook workflow is non-negotiable.** No gateless, advisory or "no-hooks" mode.
- **Stdlib-only Python and no new runtime dependencies:** no npm and no PyPI in this phase. `make`, `gh` and `jq`
  stay as they are (standing decision).
- **The setup never writes human-owned material.** It doesn't write `.aiops/config/allowed-signers`, signing keys,
  global git config or `.claude/settings.json` permission rules on the user's behalf. For those it prints exact
  commands for the human to run.
- **Rerunnable and idempotent,** with `--dry-run` (no writes) and `--yes` (non-interactive, every choice explicit).
- **It keeps working inside the plugin's own guards:**
  - the agent can't write the toolchain paths, `~/.claude/plugins` or the global git config
  - Claude Code's `/plugin` commands can't be driven from a hook or a script
- **Existing initialized repos keep working unchanged** (the 0.2.0-alpha.1 scaffold).

## Out of scope
- Phase 2 (install-state, `repair`, `upgrade`, `uninstall`, rule ids, `allowed-commands`, `/zouj-ai-sdlc:configure`)
  and Phase 3 (PyPI or `uvx` distribution, macOS and Windows support, short plugin id), per `docs/roadmap.md`.
- Supporting other harnesses (Codex, Cursor, …).
- Changing the gates, the state machine or the review personas.
- Fixing the 0.2.0-alpha.1 known issues (the CHANGELOG list); they get their own intent.
- The `sdlc setup --sandbox` trial repo: deferred to 0.2.0-alpha.3 (see Desired outcome).

## Open questions
- [x] The `solo` profile: are approvals still committed? → **Yes:** a single-file approval commit, unsigned, to keep
  the audit trail (zoujagger, 2026-11-03)
- [x] How does `sdlc setup` get the plugin installed? → **It writes the declarative
  `extraKnownMarketplaces`/`enabledPlugins` snippet into the project's `.claude/settings.json`**, and also prints the
  two `/plugin` commands (zoujagger, 2026-11-03)
- [x] The sandbox? → **A local throwaway repo:** `sdlc setup --sandbox <dir>` with a sample intent (zoujagger,
  2026-11-03). **Then deferred to 0.2.0-alpha.3** after review round 3 (zoujagger, 2026-11-04)
- [x] The release? → **0.2.0-alpha.2, on its own,** once it passes review (zoujagger, 2026-11-03)
