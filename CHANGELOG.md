# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-30

First release as a Claude Code plugin. Earlier history is the `ai-native-sdlc-template` this repo grew out of.

### Added
- **zouj-ai-sdlc Claude Code plugin** (`.claude-plugin/plugin.json`, a self-hosted `zouj` marketplace). Install with
  `/plugin marketplace add zoujagger/zouj-ai-sdlc` and `/plugin install zouj-ai-sdlc@zouj`, then `/zouj-ai-sdlc:init` per repo.
- 5-state machine over `.aiops/NNNN-slug/` artifacts: BRAINSTORMING (`intent.md`) → SPECIFICATION (`spec.md`, with DB
  schema, API contracts, data-leak flags) → PLAN, read-only (`plan.md`) → EXECUTION, autonomous TDD → PRE-REVIEW
  (`review.md` scoring report + `pr.md`).
- State engine `bin/sdlc` (stdlib Python): `status next new draft use validate approve close lock unlock init doctor`.
  The state is derived from the artifacts and git. Schemas live in `schemas/*.json`.
- Human-only gates: the exact prompt `Intent|Spec|Plan Approved NNNN` (UserPromptSubmit hook) stamps
  `approved-by/at/via/sha256` and commits the artifact alone with an `AIOps-Approval:` trailer. Editing an approved
  body re-closes the gate.
- Guards: `sdlc hook pre-edit` (gate fields, creation order, read-only lock), `sdlc hook pre-bash` (shell writes, installs,
  git staging while locked; forged approvals; merging on main), post-edit schema validation, a session-start state
  card + bootstrap skill (`using-zouj-ai-sdlc`).
- `aiops-gates.yml` CI audit (`sdlc validate --all --ci`).
- Skills `init`, `status`, `review` (writes review.md/pr.md), and `sdlc-worktree`. Evals rewritten in the
  `claude plugin eval` format. 58 deterministic engine and hook tests (`make test`).
- Docs: `docs/state-machine.md`, `docs/architecture.md` (with a threat model), and the playbook mapping in `docs/sdlc.md`.

### Changed
- Template → plugin. Skills, agents and hooks moved from `.claude/` to the plugin root and are namespaced as
  `/zouj-ai-sdlc:<skill>`. Consumer files (Makefile contract, CLAUDE.md, REVIEW.md, CI workflows, bands) moved to
  `templates/scaffold/`, copied by `sdlc init` without overwriting anything.
- Artifacts moved from `docs/intents/` to `.aiops/`. Statuses are `Draft → Approved` (previously Validated / Accepted).
  The test lock and guard lists live under `.aiops/state/` and `.aiops/config/`.
- All hooks are dormant in repos without `.aiops/`.
- `/verify` merged into `/zouj-ai-sdlc:review`; `/sdlc` renamed to `/zouj-ai-sdlc:status`.

### Fixed
- `hooks/guard-deploy.sh`: brace `${P}` in the production-gate regexes (shellcheck SC1087, latent since the template).
- CI lint is pinned to an explicit ruff rule set (`ruff.toml`: E4, E7, E9, F), so new ruff defaults can't break the build.

### Removed
- `scripts/bootstrap.sh`, `new-intent.sh`, `doctor.sh`, `validate-template.sh` and `run-evals.py` (replaced by `sdlc init`,
  `sdlc new`, `sdlc doctor`, `make check` and `claude plugin eval`). The template-only workflows have moved to the scaffold.

[Unreleased]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zoujagger/zouj-ai-sdlc/releases/tag/v0.1.0
