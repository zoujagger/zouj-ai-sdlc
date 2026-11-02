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
| The agent edits `status:`/`approved-*`/`id` | the pre-edit guard compares old and new front matter | none for Edit/Write |
| The agent runs a human-only engine command (`approve`, `close`, `unlock`, `hook`, `legacy-approvals`) | the pre-bash guard matches the command *after unquoting* (`sdl\c`, `"sdlc"`), dynamic command words (`$x approve`, `$(which sdlc) hook`), engine imports, and any change to `CLAUDECODE` / `CLAUDE_CODE_CHILD_SESSION` or `env -i`. The CLI also refuses under those markers | interpreter calls (`python -c`) aren't parsed. **Signing makes them unable to open a gate** |
| The agent writes code in states 1-3 via the shell | static write detection: redirects (heredoc-aware), `sed -i`/`awk -i inplace`, `tee`, `cp/mv -t`, `rm`, `find -delete/-exec`, installs, formatters, `git add/commit <pathspec>/apply/stash/checkout`, `git -C`, with `cd` tracking and recursion into `bash -c`/`eval` | interpreter writes aren't parsed |
| A forged approval | CI accepts an open gate only if its approval commit is single-file, carries the matching `sha256=`, isn't co-authored by Claude, and is **signed by a key in `allowed-signers` read from the target branch** (`--base`), or is listed in the target branch's `legacy-approvals` | an agent that can use an **unprotected** signing key can sign as you. Use a passphrase or `ssh-add -c`. The bootstrap PR that first adds `allowed-signers` trusts its own list (warned) and needs CODEOWNERS review |
| A PR vouches for itself | CI reads signers, the legacy list and config from the base ref. This repo also audits with the base branch's *engine* | none, given CODEOWNERS on `.aiops/config*` |
| The agent removes or rewrites `.aiops/` | `.aiops`, intent folders and their contents can't be a shell target (`rm`, `mv`, `cp`, git rm/mv/checkout/restore) in any state. A git-tracked `.aiops/` counts as initialized even if deleted | none for the parsed forms |
| A copied approved folder opens a gate for another intent | gates require front-matter `id` == folder id, and `id` is immutable | none |
| The engine can't start (python missing, a broken schema) | `hooks/engine.sh` maps any non-0/2 exit of a `pre-*` guard to a block (fail closed) | none |
| Secrets read into the session | `guard-read.sh` (Read/Grep/Glob) and guard-bash's shell readers block `defaults/secret-paths` in **every** repo. The scaffold ships `.claude/settings.json` deny rules | interpreter reads aren't parsed |
| Safety off in unrelated repos | secrets, force-push, history rewrite and prod-deploy guards are always on. Only the SDLC gates wait for `sdlc init` | none |
| The agent edits its own instructions in states 1-3 | the read-only exemption covers docs, README, CHANGELOG, CONTRIBUTING and SECURITY only. CLAUDE.md, REVIEW.md, `skills/` and `agents/` are locked | per-repo `readonly-exempt` can widen it. It's human-owned |
| An unpinned plugin in privileged CI jobs | the scaffold fetches the plugin at `ZOUJ_SDLC_REF` (`v<version>` from `sdlc init`) and loads it with `--plugin-dir` | a mutable tag. Pin a full sha |
| The approval is reused after the content changes | `approved-sha256` re-closes the gate | none |
| A review becomes stale | `commit:` plus a diff check outside `.aiops/` | none |

The local guards are a **deterrent**. The hard guarantee is the signed-approval audit. Make `aiops-gates` a required
status check, require CODEOWNERS review on `.aiops/`, and protect your signing key.

## Limits and decisions
- Plugins can't ship permission rules (plugin `settings.json` supports only `agent` and `subagentStatusLine`), so
  unattended state 4 needs allow-rules in the repo's `.claude/settings.json` (`.aiops/README.md`).
- Claude Code's own Plan mode is optional. The engine's read-only lock *is* the programmatic plan state.
- Gate approvals are per artifact. A second (tech-lead) approval for `risk: high` specs is an open question (`.aiops/0001-*/spec.md`).
