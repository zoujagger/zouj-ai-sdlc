# CLAUDE.md

This repo is the **zouj-ai-sdlc** Claude Code plugin, and it dogfoods itself: changes go through
`.aiops/NNNN-slug/{intent,spec,plan,review}.md` (`bin/sdlc status`). Docs: @docs/state-machine.md · @docs/architecture.md

## Layout
`.claude-plugin/` manifests · `skills/` · `agents/` · `hooks/` (hooks.json + bash guards) · `bin/sdlc` → `lib/sdlc_engine/`
(stdlib-only state engine) · `schemas/` · `defaults/` · `templates/{artifacts,scaffold,docs,stacks}` · `tests/` · `evals/`

## Rules
1. Follow the 5 states for anything beyond docs and typos. Never write gate statuses or `approved-*` fields yourself.
2. **Engine and guards are test-first**: add the failing case in `tests/` before changing `lib/` or `hooks/`. Every block
   message states the reason **and** the procedure.
3. Engine code is stdlib only (Python ≥ 3.9). Bash hooks must stay dormant without `.aiops/` (`aiops_enabled`) and keep
   regexes in variables, never inline in `[[ =~ ]]`.
4. Skills call `sdlc …` (it's on PATH while the plugin is enabled). Reference plugin files as `${CLAUDE_PLUGIN_ROOT}/…`.
5. Consumer-facing files live in `templates/scaffold/`, and `sdlc init` must never overwrite an existing file.
6. When code diverges from `plan.md`, log it in the Deviation log in the same commit.

## Commands
`make check` (lint + compile + tests) · `make validate` (`claude plugin validate .`) · `make dev` (`claude --plugin-dir .`) ·
`make evals` · `bin/sdlc status`

## Lessons
- The repo's own guards match command *text*: put fixture content that mentions prod deploys, merges or lock paths in files
  written with the Write tool, not in heredocs on the command line.
