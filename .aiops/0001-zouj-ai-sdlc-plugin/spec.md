---
id: 0001
title: zouj-ai-sdlc plugin
status: Draft
risk: high
intent: ./intent.md
created: 2026-10-30
---

# Spec: zouj-ai-sdlc plugin

## Summary
Turn the template into a Claude Code plugin whose state engine (`bin/sdlc`) derives each intent's lifecycle state
from `.aiops/NNNN-slug/*.md` and git, and whose hooks make the human gates and the read-only planning state
deterministic rather than advisory.

## Requirements
- **R-1** Plugin layout: `.claude-plugin/{plugin,marketplace}.json`, `skills/`, `agents/`, `hooks/hooks.json`, `bin/`.
- **R-2** State engine CLI: status, next, new, draft, use, validate (--ci), approve, close, lock, unlock, init, doctor.
- **R-3** Hooks: SessionStart (card + bootstrap skill), UserPromptSubmit (approval phrases), PreToolUse guards,
  PostToolUse validation, Stop (make check).
- **R-4** All hooks are no-ops in repos without `.aiops/`.
- Non-functional: stdlib-only engine (hooks run on every tool call); guards fail closed on crash.

## Acceptance criteria
- **AC-1**: Given the repo, when `claude plugin validate .` runs, then it passes.
- **AC-2**: Given artifacts in any combination, when `sdlc status` runs, then it reports the state (1-6, 0) and the exact next step.
- **AC-3**: Given a draft artifact, when the agent tries to approve it (Edit/Write status or approved-* fields, `sdlc approve`, an AIOps-Approval commit), then the action is blocked; when the human types exactly `Plan Approved NNNN`, then the artifact is stamped, committed alone with an `AIOps-Approval` trailer, and the state advances.
- **AC-4**: Given states 1-3 or no active intent, when the agent writes outside `.aiops/` and the exempt docs paths (Edit/Write, redirects, sed -i, installs, git add/commit of code), then it is blocked with a reason and a procedure.
- **AC-5**: Given an intent, when the agent creates spec.md before the intent is approved (or plan before spec, or review before plan), then it is blocked; new artifacts must be Draft.
- **AC-6**: Given an approved artifact, when its body changes (plan: except ticks and the Deviation log), then its gate closes again.
- **AC-7**: Given a PASS review, when code changes afterwards, then the review is reported stale; merging on main (git merge, gh pr merge) is blocked.
- **AC-8**: Given a repo without `.aiops/`, when any hook runs, then it allows everything.
- **AC-9**: Given a consumer repo, when `sdlc init` runs, then the scaffold is copied without overwriting existing files.
- **AC-10**: Given a gate opened by an agent-authored commit, when `sdlc validate --ci` runs, then it fails.
- **AC-11**: Given the existing safety guards (secrets, force push, prod deploy, test lock), when ported, then their behaviour is unchanged.

## Data model
No database. Artifact front matter (flat `key: value`): `id`, `title`, `status`, plus `approved-by`, `approved-at`,
`approved-via` (prompt | cli), and `approved-sha256` (hash of the approved body). Review: `verdict`, `commit`, `score`.
Engine state (git-ignored): `.aiops/state/active`, `.aiops/state/test-lock`. Schemas: `schemas/*.json`.

## API contracts
CLI `sdlc <command>` (exit 0 ok, 1 error). Hook entry `sdlc hook <pre-edit|pre-bash|prompt|session-start|post-edit>`
reads Claude Code hook JSON on stdin; exit 2 + stderr blocks; prompt hook prints `hookSpecificOutput.additionalContext`.

## Security & data-leak flags
- ⚠️ Local hooks are a deterrent, not a security boundary: an agent could forge state through an unguarded
  interpreter. Mitigation: the `aiops-gates.yml` CI audit plus CODEOWNERS on `.aiops/`. (zoujagger)
- ⚠️ The approval hook commits on the human's behalf, using their git identity. It commits only the approved file. (zoujagger)
- Secrets: the existing credential scanner and `.env` guards are kept.

## Architecture
Engine in `lib/sdlc_engine/` (artifacts, machine, schema, approvals, guards, cli). Bash guards are ported from
`.claude/hooks/`. Skills are rewritten to call `sdlc`. Consumer files live in `templates/scaffold/`.

## Rollout & rollback
Develop on `feat/0001-zouj-ai-sdlc-plugin`. Cutover via `.update/apply.sh`, run by the human. Rollback: `git revert` the cutover commit.

## Open questions
- [ ] Tech-lead second approval for `risk: high`? (zoujagger)
