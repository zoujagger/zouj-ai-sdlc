# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-11-02

Hardening release from the state-5 review of 0001 (`.aiops/0001-zouj-ai-sdlc-plugin/review.md`, CHANGES_REQUESTED 66/100),
delivered as intent `.aiops/0002-hardening/`.

### Security
- **Signed approvals.** Gate approvals are SSH-signed commits (`git commit -S`). `sdlc validate --ci --base <target>`
  accepts an open gate only if its single-file approval commit is signed by a key in the **target branch's**
  `.aiops/config/allowed-signers`, or listed in its `legacy-approvals`. A change can't vouch for itself.
  `require_signed_approvals` now defaults to `true`.
- **Shell guard.**
  - Heredoc redirects after the marker (`cat <<EOF > file`) no longer slip past the read-only lock.
  - Now detected: `git commit <pathspec>`, `git -C`, `cp/mv -t`, `find -delete/-exec`, `awk -i inplace`.
  - Known disguises of engine calls are blocked: `sdl\c approve`, `"sdlc"`, `$x approve`,
    `$(which sdlc) hook`, wrapper functions and aliases, `sdlc $(…)`, `xargs sdlc`, copied engines.
  - So are the known ways of changing `CLAUDECODE` / `CLAUDE_CODE_CHILD_SESSION` (`VAR=`, `unset`, `export -n`,
    `declare +x`, `env -i` / `env -`).
  - Static parsing can't be complete. The hard control is a human for each signature.
- **`.aiops/` integrity.** `.aiops`, intent folders and their files can't be deleted, moved or overwritten from the
  shell. A git-tracked `.aiops/` counts as initialized even if deleted. Gates require front-matter `id` == folder, and
  `id` is immutable.
- **Always-on safety.** Secret reads and writes, credentials, force-push, history rewrites and production deploys are
  guarded in **every** repo. Only the SDLC gates wait for `sdlc init`.
- **Secret reads.** New `hooks/guard-read.sh` covers Read/Grep/Glob on `defaults/secret-paths`, and guard-bash catches
  more shell readers of `.env` (`awk`, `sed`, `cut`, `cp`, `base64`, `xxd`, `strings`, `rg`, `< .env`, …).
- **Supply chain.** The scaffold's Claude workflows and `aiops-gates.yml` fetch the plugin at a pinned
  `ZOUJ_SDLC_REF` (set by `sdlc init`) and load it with `--plugin-dir`. This repo's CI audits with the base branch's
  engine, and pins `ruff` and `@anthropic-ai/claude-code`.

### Added
- `sdlc legacy-approvals [--write]` (human-only): records pre-signing approval commits as an explicit legacy list.
- `sdlc validate --base REF`, and `sdlc doctor` signing checks (configured key, key in `allowed-signers`, passphrase warning).
- Scaffold: `.claude/settings.json` (Read/Edit deny rules for secrets), `.aiops/config/{allowed-signers,legacy-approvals,secret-paths}`.

### Changed
- `defaults/readonly-exempt` covers docs, README, CHANGELOG, CONTRIBUTING and SECURITY only. CLAUDE.md, REVIEW.md,
  `skills/` and `agents/` are locked in states 1-3.
- State 6 DONE is reported on any branch once the PASS review is on main.
- Secret globs moved from `defaults/protected-paths` to `defaults/secret-paths`.

### Upgrading
Each approver runs `git config gpg.format ssh` and `git config user.signingkey ~/.ssh/id_ed25519.pub`, then adds
their key to `.aiops/config/allowed-signers`. Run `sdlc legacy-approvals --write` once, and re-run `sdlc init` to add
the new scaffold files (existing files are kept). See README → "Approver setup".

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

[Unreleased]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/zoujagger/zouj-ai-sdlc/releases/tag/v0.1.0
