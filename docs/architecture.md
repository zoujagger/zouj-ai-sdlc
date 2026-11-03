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
- **Gates dormant by default.** The SDLC gate hooks exit 0 when the repo has no `.aiops/`, so installing the plugin
  user-wide is safe. The safety guards (secrets, force-push, history, production, the installed plugin) are always on.
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
| A forged approval | CI accepts an open gate only if its approval commit is single-file, carries the matching `sha256=`, isn't co-authored by Claude, and is **signed by a key in `allowed-signers` read from the target branch** (`--base`), or is listed in the target branch's `legacy-approvals` | Mitigated by the **key policy**: approvals need a human for each signature (an `sk-` key, or a passphrase key not in ssh-agent). `approve` and `doctor` enforce it locally. CI can't verify key protection, so a human who weakens their key (or sets `approval_key_policy: "any"`) reopens the risk. The bootstrap PR that first adds `allowed-signers` trusts its own list (warned) and needs CODEOWNERS review |
| The agent tampers with the signing toolchain (repo git config, `.git/hooks`, the installed plugin) | the approval commit is built with plumbing (`hash-object --no-filters`, a throwaway index, `commit-tree`), by git's absolute path, with a pinned `gpg.ssh.program` (the system `ssh-keygen`), no hooks, `core.fsmonitor=false`, attributes from the empty tree and no timeout. `approve` and `doctor` refuse any repo-local or worktree config key outside a small allow-list (includes followed). The pre-bash guard blocks `git config` of signing, hook, fsmonitor, attributes, filter, include, alias and diff keys (also `git config set|unset|edit` and `-f` under `.git/`), and shell writes under `.git/` and the plugin root | the global git config, `~/.ssh` and the plugin cache are writable by anything running as you: see [Approval isolation](#approval-isolation) |
| A PR vouches for itself | CI reads signers, the legacy list and config from the base ref. This repo also audits with the base branch's *engine* | none, given CODEOWNERS on `.aiops/config*` |
| A PR rewrites the workflow that audits it | shell writes are checked against `protected-paths` (`.github/workflows/*`, `.claude/settings.json`), and the scaffold CODEOWNERS covers `/.github/` and `/.claude/` | the PR's own `aiops-gates.yml` runs. Make the audit a **required workflow** (a repository ruleset), so the base branch's copy judges every PR |
| The agent removes or rewrites `.aiops/` | `.aiops`, intent folders and their contents can't be a shell target (`rm`, `mv`, `cp`, git rm/mv/checkout/restore, `tar -x`/`unzip` into them, `find -delete` with `-name`/`-iname`/`-path`/`-ipath`) in any state. Targets are brace-expanded, and `VAR=value` set earlier in the command is substituted. Patches (`git apply`/`am`, `patch`) are read at every `-pN` strip level and under `--directory`/`-d`; piped patches are refused. A git-tracked `.aiops/` counts as initialized even if deleted | none for the parsed forms |
| A copied approved folder opens a gate for another intent | gates require front-matter `id` == folder id, and `id` is immutable | none |
| The engine can't start (python missing, a broken schema) | `hooks/engine.sh` maps any non-0/2 exit of a `pre-*` guard to a block (fail closed) | none |
| Secrets read into the session | `guard-read.sh` (Read/Grep/Glob) and `secret_scan.py` (every word of every shell command, `$(…)` included, after `~`/`$HOME`/glob expansion and `cd` tracking) block `defaults/secret-paths` in **every** repo. Recursive readers and Grep/Glob are refused on a directory that directly holds a secret directory. Writes outside the repo are checked against `secret-paths` too. The scaffold ships `.claude/settings.json` deny rules | interpreter reads aren't parsed; a secret directory two or more levels below a recursive read's root, and secret *files* (a root `.env`) under a recursive `grep -r .`; Grep inside the repo relies on `.gitignore`; variables other than `$HOME` |
| Safety off in unrelated repos | secrets, force-push, history rewrite and prod-deploy guards are always on. Only the SDLC gates wait for `sdlc init` | none |
| The agent edits its own instructions in states 1-3 | the read-only exemption covers docs, README, CHANGELOG, CONTRIBUTING and SECURITY only. CLAUDE.md, REVIEW.md, `skills/` and `agents/` are locked | per-repo `readonly-exempt` can widen it. It's human-owned |
| An unpinned plugin in privileged CI jobs | the scaffold fetches the plugin at `ZOUJ_SDLC_REF` (`v<version>` from `sdlc init`) and loads it with `--plugin-dir` | a mutable tag. Pin a full sha |
| Static shell parsing misses a form | heredoc- (incl. arithmetic and `$'…'`), quote-, glob-, brace-, variable-, `$PWD`- and `find`-aware parsing, recursion into `bash -c`/`eval`, and the known env-marker and wrapper forms | parsing can never be complete: `python -c`, base64-decoded commands, new shells, targets built by `for`, `read`, `printf -v` or `$(echo …)`, variables set outside the command, other archivers (`bsdtar`, `7z`). The key policy is what keeps a missed form from opening a gate |
| The approval is reused after the content changes | `approved-sha256` re-closes the gate | none |
| A review becomes stale | `commit:` plus a diff check outside `.aiops/` | none |

The local guards are a **deterrent**. The hard guarantee is the signed-approval audit. Make `aiops-gates` a required
status check (better: a required workflow), require CODEOWNERS review on `.aiops/`, `/.github/` and `/.claude/`, and
protect your signing key.

## Approval isolation
An approval is only as strong as the human-only step behind its signature. From strongest to weakest:
1. **Approve from a separate OS user or a clean clone** that the agent's session can't reach: a separate OS user (its
   own `~/.ssh` and global git config) or a clean clone on another machine. Nothing the agent runs can touch the key or the
   toolchain. Approve in **that user's own clean clone**, never in the agent's checkout (whose config and hooks the
   agent controls).
2. **A FIDO `sk-` key** that needs a touch per signature. Don't allow-list it with `no-touch-required`: `approve` and
   `doctor` refuse that.
3. **A dedicated signing key with a passphrase**, not used as an SSH `IdentityFile` and never added to an agent
   (`AddKeysToAgent no`). `approve` and `doctor` refuse a key that has no passphrase or is loaded in ssh-agent.

Levels 2 and 3 make every signature need you, but they run as the same user as the agent. The approval runs
`/usr/bin/git` and `python3 -I`, guards the installed plugin, and builds the commit with plumbing. Even so, anything
running as you can still change your global git config, put a program earlier on your PATH, or change `~/.ssh`, and
then capture a passphrase or redirect a touch. Against a hostile agent running as the same user, only level 1
holds.
4. **The escape hatch** `"approval_key_policy": "any"` in `.aiops/config.json` (human-owned) accepts any key. Its cost:
   anything running as you, including an agent, can sign approvals. It reopens the forged-approval risk, and the
   audit can't tell.

## Limits and decisions
- Plugins can't ship permission rules (plugin `settings.json` supports only `agent` and `subagentStatusLine`), so
  unattended state 4 needs allow-rules in the repo's `.claude/settings.json` (`.aiops/README.md`).
- Claude Code's own Plan mode is optional. The engine's read-only lock *is* the programmatic plan state.
- Gate approvals are per artifact. A second (tech-lead) approval for `risk: high` specs is an open question (`.aiops/0001-*/spec.md`).
