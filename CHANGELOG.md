# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.2.0-alpha.1] - 2026-11-03

> **Alpha, experimental.** Gates, guards and file formats may change without notice between alphas. Pin a full
> commit sha (`ZOUJ_SDLC_REF`) if you depend on exact behaviour.

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

- **A human for each signature** (`approval_key_policy`, default `"human"`): approvals and `sdlc doctor` accept
  only an `sk-` key or a passphrase-protected key that isn't loaded in ssh-agent. Approvals that need a passphrase
  are made with `bin/sdlc approve` in a terminal, and the prompt phrase tells Claude the exact command.
- The audit **fails closed** on an unresolvable or empty `--base`, and the scaffold's `aiops-gates` verifies `BASE_SHA`.
- Legacy approvals must be full shas. `legacy-approvals --write` records only commits that pass every other audit check.
- Heredoc markers count only outside quotes and comments.
- `.aiops/` protection also covers globs, `$PWD`/`$(pwd)`, `find` predicates, `tar -C` and `git apply/am`.
- Secret reads: quoting, glob words, symlinks and `~/.ssh` / `~/.aws` / `.netrc` / `.npmrc` are covered. The
  `.env.example` exemption is per word.
- Force-push through a `+refspec`, `git --work-tree`, and `curl -o` / `wget -O` are caught.
- **Signing toolchain.** Approval commits run with a pinned `gpg.ssh.program`, `core.hooksPath=/dev/null` and no
  timeout. Repo-local `gpg.*`, `user.signingkey` and `core.hooksPath` are refused, and the agent can't set them or
  write under `.git/` or the installed plugin.
- **Secrets and protected paths.** `secret-paths` apply to every shell argument and to directory Grep/Glob, with
  cloud, registry and cluster credentials added. `protected-paths` apply to shell writes, and the scaffold CODEOWNERS
  covers `/.github/` and `/.claude/`.
- **Parser.** Heredoc markers inside arithmetic and `$'…'` don't hide later lines. Targets are brace-expanded and
  `VAR=value` set earlier in the command is substituted. Patches are read at every `-pN` level and under
  `--directory`; piped patches (`git apply`, `git am`, `patch`) are refused. `tar -x`/`unzip -d` destinations and
  `find -iname`/`-ipath` count.
- **Variants and false positives.** Quoted `ENV="prod"`, `'+main'`, `git push -fu` and `git push --mirror` are
  blocked. `echo $HOME close …`, `[ "$CLAUDECODE" = 1 ]` and commit messages that merely mention `AIOps-…Approval`
  are no longer blocked.
- **Legacy and keys.** `legacy-approvals --write` records only unsigned approvals on main that predate the commit
  introducing `allowed-signers`, and confirms each one (`--yes` skips the question). An `sk-` key allow-listed with
  `no-touch-required` fails the key policy. This repo's CI fails closed on an unresolvable base.
- **Approval commit by plumbing.** The approval is hashed without filters, built in a throwaway index and signed with
  `commit-tree`, by git's absolute path, with `core.fsmonitor=false` and attributes from the empty tree: nothing
  configured in the repo (or globally) runs inside it. Repo-local config is limited to an allow-list (includes
  followed), and the guard blocks `git config` of fsmonitor, attributes, filter, include, alias and diff keys, the
  `git config set|unset|edit` form and `-f` under `.git/`.
- **Wrapped engine calls.** `eval`, `sh -c`, `nice`, `timeout`, `xargs`, `!` and `{ …; }` in front of a dynamic command
  word, computed marker names (`unset ${a}CODE`) and `m=AIOps-Approval; … "$m:"` are blocked.
- **Secret reads, one pass.** `lib/sdlc_engine/secret_scan.py` replaces the per-word bash loop (about 60 ms instead of
  up to 835 ms): globs, `$(…)`, `cd`, `$HOME` and ancestor directories are covered, and commit/PR messages, grep
  patterns and heredoc bodies no longer cause false blocks. Writes outside the repo are checked against `secret-paths`.
- **Setup hints** use `git config --global` and a dedicated `~/.ssh/aiops_signing` key, and refusals print the
  plugin's absolute `bin/sdlc approve` command (consumer repos have no `bin/sdlc`).
- `git checkout/restore` respect `protected-paths`; `tar -C<dir>` and git's C-quoted patch names count.
- **Round 4.** Engine calls behind loops, `trap`, `coproc`, glob/brace command words (`bin/sdl?`), absolute shell
  paths and text piped into a shell are blocked, and so are brace-, glob- and printf-built marker names and
  `exec -c`. Edit/Write into the installed plugin is blocked in every repo, and the engine runs as `python3 -I`.
  `find` feeding a reader counts as a recursive read. GitHub CLI and git-credential files are secret paths.
  Approvals refuse symlinked artifacts and report a busy index. The round-3 `-b`/`-u` false negatives and false
  positives are fixed.
- **Round 5.** The engine-call rule is per command again (no blocks on `$GIT commit -m "…close…"`). `curl -F
  file=@.env` / `--data-binary @.env` uploads and credential printers (`gh auth token`, `git credential fill`, …)
  are blocked. `git checkout <rev> -- .` and `git restore -s <rev> ':/'` are refused. Git's global config, shell
  startup files, `~/.local/bin`, `~/bin` and `~/.claude/plugins` can't be written by the agent
  (`defaults/toolchain-paths`). `bin/sdlc` starts through a POSIX `sh` line that runs `python3 -I`.
- **Round 6.** Toolchain targets are resolved (symlinks, directory destinations such as `cp x ~/.local/bin/`), and
  every user-writable PATH directory counts. The engine runs git, ssh-keygen and python by absolute path, and the
  documented approve command is `/usr/bin/python3 -I <plugin>/bin/sdlc approve …`. More credential printers
  (`git -C . credential fill`, `kubectl config view --raw`, `aws configure export-credentials`, …) are blocked.
- **Round 7.** `$HOME`, `${HOME}`, `$XDG_CONFIG_HOME` and `~` in shell write targets reach the out-of-repo guards.

### Known issues (alpha; planned for 0.2.0-alpha.2)
- This repo itself runs `"approval_key_policy": "any"` with a passphrase-less key (a logged human decision), so a
  shell-parser bypass can forge an approval here. Consumer repos default to `"human"`.
- Shell writes to toolchain files (`~/.bashrc`, PATH directories) are guarded only in initialized repos; Edit/Write
  is guarded everywhere. Symlinked toolchain *files* (nvm/pipx shims, stow-managed dotfiles) are checked by their
  resolved target only, and a PATH directory created in the same command isn't covered.
- Missing: `~/.zlogin`, `~/.inputrc` in toolchain-paths; `op item get`, `op inject`, `vault read`,
  `aws sts get-session-token`, `kubectl get secret -o yaml`, `security find-generic-password -w`, `pass show` as
  credential printers; `curl -d@.env` (attached) and `--data-urlencode name@.env`; `rg -uu KEY .` and `grep -r KEY`
  over a cwd holding `.env`.
- Approve calls built after a variable assignment (`s=sdlc; $s $'approve'`, `"${a-approve}"`, `"${a[@]}"`,
  `$(echo approve)`) are not caught; under `"human"` they still need the human's passphrase or touch.
- `git checkout <rev> -- ..` from a subdirectory or with an absolute path isn't treated as a whole-tree rewrite, and
  the whole-tree rule also fires in other repos under `/tmp`.
- False positives: `mkdir -p ~/.local/bin`; prose that mentions a credential printer (`git commit -m "never run gh
  auth token"`); `timeout 30 $X close` (on purpose: the shape of `timeout 5 $s approve`).
- The toolchain check exists in both bash (guard-files.sh) and Python (guards.py).

### Added
- `sdlc legacy-approvals [--write [--yes]]` (human-only): records pre-signing approval commits as an explicit legacy list.
- `sdlc validate --base REF`, and `sdlc doctor` signing checks (configured key, key in `allowed-signers`, passphrase warning).
- Scaffold: `.claude/settings.json` (Read/Edit deny rules for secrets), `.aiops/config/{allowed-signers,legacy-approvals,secret-paths}`.

### Changed
- `defaults/readonly-exempt` covers docs, README, CHANGELOG, CONTRIBUTING and SECURITY only. CLAUDE.md, REVIEW.md,
  `skills/` and `agents/` are locked in states 1-3.
- State 6 DONE is reported on any branch once the PASS review is on main.
- Secret globs moved from `defaults/protected-paths` to `defaults/secret-paths`.

### Upgrading
Each approver creates a dedicated key and runs `git config --global gpg.format ssh` and
`git config --global user.signingkey ~/.ssh/aiops_signing.pub` (repo-local signing settings are refused), then adds
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

[Unreleased]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.2.0-alpha.1...HEAD
[0.2.0-alpha.1]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.1.0...v0.2.0-alpha.1
[0.1.0]: https://github.com/zoujagger/zouj-ai-sdlc/releases/tag/v0.1.0
