# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).
This file is maintained with `/release` (release-manager agent).

## [Unreleased]

### Added
- `make doctor` (`scripts/doctor.sh`): setup health check that prints the fix for every problem, including unwired Makefile targets.
- `/help-me "<goal>"` skill: maps a free-text goal to the right command. `/onboard` is now an interactive, role-based tour that starts from `make doctor`.
- README "Start here" task table and a "Which agent does what" table in `docs/sdlc.md`.
- `docs/examples/`: a complete worked intent → spec → plan (`0001-csv-export`) and sample `CLAUDE.md` project notes per stack.
- `SDLC_HOOK_PROFILE=strict|standard|spike` for the inner-loop hooks (format/lint, definition of done). Safety guards ignore it,
  enforced by `validate-template` and the `spike-profile-keeps-prod-gate` eval. The session-start hook flags an unwired Makefile.
- Stack presets (`templates/stacks/*.recipes`) for Python, Node and Go, applied with `scripts/bootstrap.sh <name> [org] --stack <stack>`.
- Initial AI-native SDLC template.
- Intent-driven workflow aligned with Anthropic's AI-Native SDLC Playbook: `intent.md` → `spec.md` → `plan.md` in `docs/intents/`.
- Skills `/intent`, `/plan`, `/parallel`, `/fix`, `/verify`, `/deploy`, `/triage`, `/learn`, plus advisory policy skills (security, compliance, UX, brand).
- Agents `verifier` (fresh-context verification) and `diagnostician` (Maintain-stage diagnosis).
- Hooks `guard-tests` (test lock during bug fixes) and `guard-deploy` (production gate). Format and lint after every edit.
- `REVIEW.md` (3-pass PR review), continuous evals (`evals/`, `claude-evals.yml`), control bands (`ops/bands.yaml`, `claude-maintain.yml`),
  `deploy.yml` with gated production and single-command rollback, `docs/governance.md`, managed-settings example.

### Fixed
- `scripts/bootstrap.sh` no longer requires `jq` (optional, hooks fall back to python3), works with BSD/macOS `sed`, and suggests the native Claude Code installer.

### Removed
- `/prd`, `/design`, `/plan-tasks`, `/tdd`, `/test` and the PRD/design/tasks templates, replaced by the intent/spec/plan flow.
