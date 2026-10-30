# Architecture

```
Claude Code session
 ├─ SessionStart ─────────▶ sdlc hook session-start  → state card + skills/using-zouj-ai-sdlc body
 ├─ UserPromptSubmit ─────▶ sdlc hook prompt         → "Plan Approved NNNN" ⇒ approvals.approve() ⇒ commit
 ├─ PreToolUse Bash ──────▶ guard-bash.sh · guard-deploy.sh · sdlc hook pre-bash   (exit 2 = block)
 ├─ PreToolUse Edit|Write ▶ guard-files.sh · guard-tests.sh · sdlc hook pre-edit
 ├─ PostToolUse Edit|Write▶ sdlc hook post-edit (schema) · post-edit-format.sh (make format/lint)
 └─ Stop ─────────────────▶ stop-verify.sh (make check; releases the /fix test lock)

lib/sdlc_engine/
  artifacts.py   front matter, sections, checkboxes, approval hash (stdlib only)
  machine.py     project root, config, active intent, gate(), evaluate() → Status, lock()
  schema.py      validate() against schemas/*.json + cross-artifact checks
  approvals.py   approve(), close(), audit() (CI)
  guards.py      check_edit() (simulates Edit/Write/MultiEdit), check_bash() (static write detection)
  cli.py         `sdlc` commands and the hook dispatcher
```

## Design choices
- **Derived state, Markdown as the source of truth.** Humans read and edit the artifacts, machines validate them.
  Git versions both the artifacts and the approvals.
- **Skills advise, hooks decide.** The skills (Superpowers-style: trigger descriptions, checklists, red-flag tables)
  make violations rare. The hooks make the important ones close to impossible.
- **Dormant by default.** Every hook exits 0 when the repo has no `.aiops/`, so installing the plugin user-wide is safe.
- **Fail closed.** If the gate guard crashes, it blocks the call and says so, because a guard that errors must never silently allow.
- **Stdlib only.** Hooks run on every tool call, so the engine needs no `pip install` and starts fast.
- **Approval through the prompt.** A tool call can't author a user prompt, so a phrase typed as the whole prompt is the
  cleanest proof of human intent available inside a session. `CLAUDECODE=1` is set for hooks too, so the CLI's
  `approve` refuses it, while the prompt hook calls the engine in-process.

## Threat model
| Threat | Mitigation | Residual |
|---|---|---|
| The agent edits `status:`/`approved-*` | the pre-edit guard compares old and new front matter | none for Edit/Write |
| The agent runs `sdlc approve`, `sdlc hook prompt`, or imports the engine | the pre-bash guard, plus the CLI refusing under `CLAUDECODE` | an obfuscated interpreter call could slip through |
| The agent writes code in states 1-3 via the shell | static write detection (redirects, `sed -i`, `tee`, `cp/mv/rm`, installs, git) | `python -c "open(...).write()"` and similar aren't parsed |
| A forged approval commit | the pre-bash guard blocks `AIOps-Approval` text. CI requires the approval commit to touch only that artifact, to carry the matching `sha256=`, and not to be co-authored by Claude. With `require_signed_approvals`, it must also be signed | without signing, a local actor who crafts a single-file commit (e.g. `git commit -F`) can pass. Turn on signing plus CODEOWNERS on `.aiops/` |
| The agent deletes or restores an artifact through git | `git rm/mv/checkout/restore/reset/stash` on `.aiops/*` artifacts is always blocked | none for the listed subcommands |
| The engine can't start (python missing, a broken schema) | `hooks/engine.sh` maps any non-0/2 exit of a `pre-*` guard to a block (fail closed) | none |
| Repos without `.aiops/` | **every** hook is dormant, including the secrets, force-push, prod-deploy and test-lock guards from the old template | by design, so a user-wide install never blocks unrelated repos. Run `sdlc init` to opt in |
| The agent edits its own instructions in states 1-3 | `*.md` is read-only-exempt by default, which includes `CLAUDE.md` and, in this repo, `skills/` and `agents/` | narrow `readonly-exempt` per repo if that matters. Behaviour files are covered by CODEOWNERS |
| The approval is reused after the content changes | `approved-sha256` re-closes the gate | none |
| A review becomes stale | `commit:` plus a diff check outside `.aiops/` | none |

The local guards are a **deterrent with audit**, not a security boundary. Treat `aiops-gates` as a required status
check and require CODEOWNERS review on `.aiops/` for the hard guarantee.

## Limits and decisions
- Plugins can't ship permission rules (plugin `settings.json` supports only `agent` and `subagentStatusLine`), so
  unattended state 4 needs allow-rules in the repo's `.claude/settings.json` (`.aiops/README.md`).
- Claude Code's own Plan mode is optional. The engine's read-only lock *is* the programmatic plan state.
- Gate approvals are per artifact. A second (tech-lead) approval for `risk: high` specs is an open question (`.aiops/0001-*/spec.md`).
