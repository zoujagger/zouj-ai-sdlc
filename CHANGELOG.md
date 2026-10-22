# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).
This file is maintained with `/release` (release-manager agent).

## [Unreleased]

### Added
- Initial AI-native SDLC template.
- Intent-driven workflow aligned with Anthropic's AI-Native SDLC Playbook: `intent.md` → `spec.md` → `plan.md` in `docs/intents/`.
- Skills `/intent`, `/plan`, `/parallel`, `/fix`, `/verify`, `/deploy`, `/triage`, `/learn`, plus advisory policy skills (security, compliance, UX, brand).
- Agents `verifier` (fresh-context verification) and `diagnostician` (Maintain-stage diagnosis).
- Hooks `guard-tests` (test lock during bug fixes) and `guard-deploy` (production gate). Format and lint after every edit.
- `REVIEW.md` (3-pass PR review), continuous evals (`evals/`, `claude-evals.yml`), control bands (`ops/bands.yaml`, `claude-maintain.yml`),
  `deploy.yml` with gated production and single-command rollback, `docs/governance.md`, managed-settings example.

### Removed
- `/prd`, `/design`, `/plan-tasks`, `/tdd`, `/test` and the PRD/design/tasks templates, replaced by the intent/spec/plan flow.
