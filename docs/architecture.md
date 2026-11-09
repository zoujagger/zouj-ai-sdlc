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
  rules.py       the rule registry (defaults/rules, rules.md), `sdlc why`, exact-command allowances
  lifecycle.py   install-state, adoption (defaults/scaffold-history.json), list-installed/repair/upgrade/uninstall
  migrations.py  migrations upgrade lists (legacy-approvals: human-only)
  cli.py         `sdlc` commands and the hook dispatcher
```

## Design choices
- **Derived state, Markdown as the source of truth.** Humans read and edit the artifacts, machines validate them.
  Git versions both the artifacts and the approvals.
- **Skills advise, hooks decide.** The skills (Superpowers-style: trigger descriptions, checklists, red-flag tables)
  make violations rare. The hooks make the important ones close to impossible.
- **Gates dormant by default.** The SDLC gate hooks exit 0 when the repo has no `.aiops/`, so installing the plugin
  user-wide is safe. The safety guards (secret reads, force-push, history, production, and Edit/Write and shell writes to secrets
  outside the repo, the toolchain and the installed plugin) are always on: in a repo without `.aiops/`,
  `engine.sh` still runs `pre-bash`, and `check_bash` runs only those safety checks (`gates=False`).
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
| The agent deletes a protected tree, or brings protected config in from elsewhere | **G-FILE-05**: a delete or move target (`rm`, `rmdir`, `unlink`, `shred`, `mv` sources, an unfiltered `find -delete`) that is the repo, a directory above it or above home, or a directory holding a protected-paths glob or a git-tracked protected or secret file. **G-FILE-06**: `tar -x`/`unzip` into the repo are judged by their member names (stdlib `tarfile`/`zipfile`); `git stash pop/apply`, `git merge/rebase <ref>` and `git cherry-pick` by the paths they bring in; a change to `.aiops/config*`, install-state, `.claude/settings.json` or a protected path is refused unless it comes from main (`origin/<main>`). `git pull` off main is refused: it can't be inspected before it fetches. Wrappers (`nice`, `timeout 5`, `sudo -u x`, …), nested commands (`sh -c`, `trap`, `coproc`, `watch`, `parallel`, `flock -c`, `find -exec`, rebase `--exec`, git aliases), option values, every merge operand, cherry-pick ranges, `--strip-components`, link members, filtered and negated `find`, `pushd`, symlinks made in the same command, `rsync --delete`/`--remove-source-files`, and archives or refs changed earlier in the same command are seen through or refused | dynamic command words (`x=env; $x`) and interpreter writes aren't parsed; untracked secrets below a deleted directory aren't walked; other archivers (`bsdtar`, `7z`) aren't parsed; "main" is trusted by its local refs (merges from it, and cherry-picks of commits already on it), which the agent could move (CI reads config from the base branch). Still open, intent 0006: git command keys and variables not yet known (`protocol.ext.allow`, `core.gitProxy`, `remote.*.uploadpack`, `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT/KEY/VALUE`), `find -fprint`, `${@:1}`/array positional forms, `cpio -pdl`, downloads with an unknown name (`wget -i`, `--content-disposition`, `curl -J`), `aria2c`/`http`, clone's default directory, `cp -s` farms, `GIT_SSH` program files, G-ENV-05 false positives when a `/proc` read and an unrelated glob share one line, git plumbing (`update-index`, `checkout-index`, `read-tree`), `switch`/`checkout <branch>`/`reset`/`revert`, environment dumps by `export`/`declare`/`set`/`ps e`, case-insensitive filesystems, the human-only checks in repos without `.aiops/`, and three parse forms found in 0005 review round 9 that main shares: `)#<<EOF` (a `<<` in a comment after `)` skips the following lines), a stuck operator before a redirection (`true&&>/dev/null cmd` merges `cmd` into the previous command), `$'…'` in a heredoc delimiter, and assignments that bash makes in a subshell of its own (pipeline members `d=x | cat`, `&` jobs) or only conditionally (`false && d=x`, a `case` arm) |
| A copied approved folder opens a gate for another intent | gates require front-matter `id` == folder id, and `id` is immutable | none |
| The engine can't start (python missing, a broken schema) | `hooks/engine.sh` maps any non-0/2 exit of a `pre-*` guard to a block (fail closed) | none |
| Secrets read into the session | `guard-read.sh` (Read/Grep/Glob) and `secret_scan.py` (every word of every shell command, `$(…)` included, after `~`/`$HOME`/glob expansion and `cd` tracking) block `defaults/secret-paths` in **every** repo. Recursive readers and Grep/Glob are refused on a directory that directly holds a secret directory. Edit/Write and shell writes outside the repo are checked against `secret-paths` too, in every repo. The scaffold ships `.claude/settings.json` deny rules | interpreter reads aren't parsed; a secret directory two or more levels below a recursive read's root, and secret *files* (a root `.env`) under a recursive `grep -r .`; Grep inside the repo relies on `.gitignore`; variables other than `$HOME` |
| Safety off in unrelated repos | secret reads, force-push, history rewrite and prod-deploy guards, and Edit/Write of secrets, the toolchain and the installed plugin are always on. Only the SDLC gates wait for `sdlc init` | interpreter writes (`python -c`) and the other forms static parsing misses; signing and the CI audit keep such tampering from opening a gate silently |
| The agent edits its own instructions in states 1-3 | the read-only exemption covers docs, README, CHANGELOG, CONTRIBUTING and SECURITY only. CLAUDE.md, REVIEW.md, `skills/` and `agents/` are locked | per-repo `readonly-exempt` can widen it. It's human-owned |
| An unpinned plugin in privileged CI jobs | the scaffold fetches the plugin at `ZOUJ_SDLC_REF` (`v<version>` from `sdlc init`) and loads it with `--plugin-dir` | a mutable tag. Pin a full sha |
| Static shell parsing misses a form | heredoc- (incl. arithmetic and `$'…'`), quote-, glob-, brace-, variable-, `$PWD`- and `find`-aware parsing, recursion into `bash -c`/`eval`, and the known env-marker and wrapper forms | parsing can never be complete: `python -c`, base64-decoded commands, new shells, targets built by `for`, `read`, `printf -v` or `$(echo …)`, variables set outside the command, other archivers (`bsdtar`, `7z`), env markers overridden by `printf -v`/`read`/`+=`, subcommands assembled from pieces (`$'approve'`, `app$(echo r)ove`, `${a}ove`), `base64 -d | bash`, `bash < file`, a `#` and a quote both nested inside `"$(…)"` (the pre-pass reads the inner quote as closing the outer one; also on main). The key policy is what keeps a missed form from opening a gate |
| The agent uses `sdlc setup` to downgrade the profile or write a human-owned file | run under the agent (`CLAUDECODE` / `CLAUDE_CODE_CHILD_SESSION`), setup never changes an existing `.aiops/config.json` or `.claude/settings.json`, creates a missing config with init's defaults, and prints the rest as human steps. It and `init` write only regular files at the top of a git repo (git's `GIT_DIR`/`GIT_WORK_TREE`-style variables are refused), never through a link, and never in `$HOME`, `~/.claude` or a toolchain path. Under the agent, `init --force` keeps every file the guard won't let the agent write. They scaffold only the repo they run in (a `CLAUDE_PROJECT_DIR` naming another repo is refused), and home is taken from the account record as well as `$HOME`. The pre-bash guard allows the agent's `sdlc init|setup` only in the session's repo (`CLAUDE_PROJECT_DIR`), without `cd`, `-C`, `--chdir`, `-execdir` or `GIT_*`/`CLAUDE_PROJECT_DIR`/`HOME` settings | the check reads the env markers, so an interpreter that strips them runs setup as the human; dynamic command words (`$x setup`), `bash -c "$(…)"`-built commands, brace-expanded `{cd,…}`, `unset CLAUDE_PROJECT_DIR` and other directory-changing wrappers aren't parsed. Setup flags an uncommitted or staged human-owned file whose content isn't what it writes, but a file already committed counts as reviewed, so one the agent committed before `init` (when the guards are off) isn't flagged: a **deterrent**. CI reads the config from the base ref, so a downgrade can't open a gate |
| A false-positive allowance lifts a gate | `.aiops/config/allowed-commands` is human-owned (`.aiops/config*`, CODEOWNERS). Only `heuristic` rules (G-ENV-03, G-BASH-07) consult it, through `rules.allowed`: an exact, single-line, byte-equal command, one rule per entry, every other rule still evaluated; never a whole-environment dump. A symlinked file is ignored, and doctor never echoes an unrecognised line. Gate, secret, toolchain and safety rules call `block` directly and never reach it. `doctor` and `validate --ci` (head and base) reject other entries | an allowed `sudo` command can write root-owned PATH directories (`sdlc why G-BASH-07` warns) |
| The agent edits install-state to steer a lifecycle command | `.aiops/install-state.json` is in `defaults/protected-paths` and `guards.GUARDED_RE` (Edit/Write and shell writes blocked) and under CODEOWNERS. It never decides a gate (CI ignores it) | none for the parsed forms |
| `uninstall` as a deletion primitive | human-only (CLI refuses under the agent; the pre-bash guard blocks a real `uninstall`, G-GATE-07). A path is removed only if it is recorded, a scaffold path of some release, and unmodified; `.aiops/NNNN-*` and `.aiops/state` are refused whatever install-state says; removal never follows a link | a human who runs it removes the files it lists (`--dry-run` shows them) |
| The agent's `upgrade`/`repair` rewrites the CI audit, settings or locked code | run by the agent they write only what the agent could write itself (`cli._agent_blocked`: not human-owned, not protected, not code under the read-only lock) and print the human's terminal command for the rest; they run only in the session's repo (G-SCAF-01), and an inline `SDLC_HOOK_PROFILE=`/`AIOPS_INTENT=` can't lift the lock for them (the guard refuses the line; the engine judges the lock without them) | the pinned sha comes from `installed_plugins.json` or the plugin checkout, both writable by the user; it lands only in human-owned files the human reviews |
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
