# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · Versioning: [SemVer](https://semver.org/).

## [Unreleased]

Planned as **0.2.0-alpha.4**: the shell-write guard gaps from the 0.2.0-alpha.3 known issues, delivered as intent
`.aiops/0005-guard-gaps/`. Almost every change adds blocks. Two exceptions loosen a check: `find . -type d -delete`
(removes only empty directories) and `git cherry-pick` of a commit already on main are allowed.

### Security
- **Deleting a protected tree is blocked in every state (`G-FILE-05`).** This covers the repo itself, a directory
  above it or above home, and a directory holding a protected path or a git-tracked protected or secret file (`rm -rf ./`,
  `rm -rf "$PWD"`, `rm -rf ..`, `mv .github …`, `rm -rf .claude`). Untracked trees such as `node_modules` aren't
  walked, and a filtered `find -delete` is unaffected.
- **Protected config can't be brought in from elsewhere (`G-FILE-06`).** Archives are judged by their member names;
  `git stash pop|apply`, `git merge|rebase <ref>` and `git cherry-pick` by the paths they bring in. Main and
  approval commits pass. `git pull` off main is refused: `git fetch`, then `git merge <ref>`.
- **Safety checks in every repo.** In a repo without `.aiops/`, shell writes to the approval toolchain, the installed
  plugin, secrets outside the repo and `git config --global` signing keys are blocked (as Edit/Write were). It costs
  one python start per Bash call there, like the secret scan. SDLC gates stay dormant.
- **Every spelling of an environment dump.** `/usr/bin/env`, `e''nv`, `"printenv"` and `\env` are G-ENV-03. Reading
  `/proc/*/environ` is the new secret rule `G-ENV-05`.
- **G-ENV-03 allowances accept only safe forms:** `printenv NAME…`, or a command that doesn't run env/printenv
  (`ls env`, `python -m venv env`). `source`/`.` run their argument and are refused. The list of known dumps is gone.
- **The agent's `sdlc init --force`** judges the read-only lock without `SDLC_HOOK_PROFILE` / `AIOPS_INTENT`.
- **Wrappers no longer hide a write.** `nice`, `timeout 5`, `stdbuf`, `setsid`, `ionice`, `sudo -u x`,
  `command -p`, `flock f`, `xargs`, `busybox` and the like are seen through by every shell rule, including the
  read-only lock. This hole predates 0005.
- **The shell parser reads commands as bash does.** It is shared by the guards and the always-on secret scan.
  Comments and heredoc bodies are dropped exactly; a heredoc delimiter is a bash word (`<<E-O`, `<<'E'OF`), and a
  missing delimiter line hides nothing. Backslash-newline continuations are joined and `$'…'` is decoded.
  `)>file`, `!`/`{` after keywords, `time -p`, `function f {` and `\\;` split commands correctly, while `find`'s `\;` stays a word. A subshell's
  `cd` stays inside it, and a `case` pattern's `)` isn't a subshell end. When a comment is dropped, the line is also
  judged with every `#` kept as a word (as before), so a separator that a misread comment hid still splits. Only the
  unquoted, unescaped `case`/`in`/`esac` keywords, not after a redirection, drive case parsing; pattern words are
  judged too, and a line with a `case` is also judged without case tracking. A line with a subshell is also judged as
  before, with every `cd` persisting, so scope tracking can only add blocks. The cost: a relative delete after a
  `case` or a quoted `)` inside a subshell is judged from the outer directory as well.
- Fixes the 0.2.0-alpha.3 known issues about `rm -rf ./` and parent-directory deletes, shell writes in repos without
  `.aiops/`, and G-ENV-03's list of known dumps.

### Changed
- `git pull` is refused off the main branch (G-FILE-06): `git fetch`, then `git merge <ref>`, which is inspected.
- A G-ENV-03 allowance must be safe in every simple command; `source`/`.` and secret-named `printenv` are refused.

## [0.2.0-alpha.3] - 2026-11-06

> **Alpha, experimental.** Gates, guards and file formats may change without notice between alphas.

Roadmap Phase 2 (`docs/roadmap.md`), delivered as intent `.aiops/0004-safe-lifecycle/`: the plugin now knows what it
installed, upgrades and repairs a repo safely, and explains every block. The playbook workflow is unchanged.

### Added
- **Rule ids and `sdlc why <id>`.** Every block reads `BLOCKED [G-AREA-NN] by <hook>: …` and ends with
  `sdlc why <id>`. The command explains the reason, the stage the rule protects and the safe alternative. The
  registry is `defaults/rules` (64 rules, each in one class: gate, secret, toolchain, safety or heuristic) plus
  `defaults/rules.md`.
- **Exact-command allowances.** `.aiops/config/allowed-commands` (human-owned) can let one exact command through one
  `heuristic` rule. Only two rules are heuristic: `G-ENV-03` (env/printenv) and `G-BASH-07` (sudo, mkfs, dd,
  chmod 777). Every other rule still runs on that command. `sdlc doctor` and `sdlc validate --ci` reject entries for
  any other rule, an unknown id or a command with control characters. There is no per-rule disable switch.
- **`.aiops/install-state.json`.** `init` and `setup` record the plugin version, the CI ref, the profile, the stack,
  and a hash of each file they wrote. The engine writes it; the agent can't (protected path, CODEOWNERS).
- **`sdlc list-installed`.** Shows each installed file as current, stale, modified, missing, unmanaged, dropped or new.
- **`sdlc repair [--dry-run] [--yes]`.** Restores missing files.
- **`sdlc upgrade [--dry-run] [--yes]`.** Brings the scaffold to the running plugin version:
  - replaces stale files, showing a diff
  - creates new files
  - keeps modified files, except for the CI ref
  - pins every ref to the plugin's full commit sha, from `installed_plugins.json` or a pushed checkout
  - lists migrations; `legacy-approvals` is human-only and is never run for you
- **`sdlc uninstall [--dry-run] [--yes]`.** Human-only. Removes unmodified scaffold files, never `.aiops/NNNN-*`.
- **`upgrade` changes only the plugin's own refs:** literal `ZOUJ_SDLC_REF` values (an expression is left alone and
  reported) and the zouj marketplace's `ref` in JSON (another marketplace is never touched). Each pin is shown as a
  diff before you confirm. After adoption, a scaffold file you had deleted is `declined` and never re-created.
- **Adoption.** Repos from 0.1.0, 0.2.0-alpha.1 and alpha.2 are adopted from `defaults/scaffold-history.json`, which
  `scripts/scaffold-history.py` generates from the release tags.
- **`/zouj-ai-sdlc:configure`.** Shows the profile and installed files and previews a profile change, then hands you
  the terminal command.
- **Tests.** `tests/test_playbook.py` runs the agent's `upgrade` and `repair` in states 1, 4 and 5 of every profile
  walk and requires no change to any gate, artifact or the lock. A permanent test breaks `upgrade` on purpose and
  checks that each break is caught.

### Changed
- `G-ENV-04` (secret): `echo $…TOKEN/KEY/SECRET/PASSWORD` is now a separate rule from env dumping.
- The post-edit schema check reads `NOT VALID [G-ART-09] … was saved` (the edit had already landed).
- Run by the agent, `sdlc upgrade|repair|uninstall` act only on the session's repo (G-SCAF-01). A real `uninstall` is
  blocked (G-GATE-07).
- `docs/architecture.md` no longer claims that shell writes to the toolchain and secrets are guarded in repos without
  `.aiops/`.

### Known issues (planned for intent 0005)
- In states 4-5 the shell-write check misses `rm -rf ./`, `rm -rf "$PWD"`, `rm -rf .github/workflows` and
  `mv .github …`. Protected paths are matched exactly, not as a parent directory.
- In a repo without `.aiops/`, shell writes to `~/.gitconfig`, `~/.bashrc`, `git config --global`, the installed
  plugin and `~/.ssh` aren't checked. Edit/Write to them is. Signing and the CI audit keep such writes from opening a
  gate.
- `sdlc doctor` doesn't report install-state yet. Use `sdlc list-installed`.
- G-ENV-03's whole-environment check works from a list of known forms: nested forms (`bash -c env`, `env env`,
  `xargs env`, `if …; then env; fi`) aren't recognised, so a human who writes one of them into `allowed-commands`
  lets the environment through. `re_dump_env` also doesn't match `/usr/bin/env` or `cat /proc/self/environ`.

### Upgrading from 0.2.0-alpha.2
Update the plugin with `/plugin`, then run `sdlc upgrade --dry-run` and `sdlc upgrade` in your own terminal. Your
repo is adopted first (only install-state is written), and every `ZOUJ_SDLC_REF` is pinned to a full sha. Commit
the result through a PR.

## [0.2.0-alpha.2] - 2026-11-04

> **Alpha, experimental.** Gates, guards and file formats may change without notice between alphas.

Roadmap Phase 1 (`docs/roadmap.md`), delivered as intent `.aiops/0003-guided-setup/`: a newcomer gets from nothing to a
first approved intent with one guided, rerunnable command, and the playbook workflow is the same in every profile.

### Added
- **`sdlc setup` and `/zouj-ai-sdlc:setup`.**
  - Steps: preflight → inventory → plan → gate summary → one confirmation → apply → the human steps → doctor.
  - Preflight blocks on missing git, make or python ≥ 3.9. It warns, with the fix, about Claude Code < 2.1, `gh`
    login and the `workflow` scope, and a missing git credential helper.
  - `--dry-run` writes nothing, and without `--yes` or a terminal setup writes nothing (exit 2).
  - Rerunning changes nothing when everything is in place.
- **Profiles `solo`, `team` and `strict`.** They change only how a human approval is proven:
  - `solo`: unsigned approval commits
  - `team`: SSH-signed, a human per signature
  - `strict`: an `sk-` key touch, plus CODEOWNERS on `/.aiops/`

  The new `"sk"` key policy backs `strict`. An unknown `approval_key_policy` is now refused instead of behaving like
  `"any"`. Config gains `profile` (default `team`), and doctor shows it.
- **Human-owned files stay human.** Run by the agent, setup never changes an existing `.aiops/config.json` or
  `.claude/settings.json`: it prints the exact JSON for the human. Run by a human, it merges only its own keys,
  showing a diff.
- **Collaborators are offered the plugin.** The scaffold's `.claude/settings.json` carries the marketplace snippet
  (`extraKnownMarketplaces` and `enabledPlugins`).
- **`sdlc feedback`.** Issue links and a doctor summary with paths reduced to the repo name; it sends nothing.
- **Docs.** A task-first README (Start using, install paths A/B/C, profiles, a throwaway-repo recipe to try it), `COMMANDS-QUICK-REF.md`,
  `TROUBLESHOOTING.md`, and the `install-problem` and `quick-feedback` issue forms.
- **`tests/test_playbook.py`.** The full playbook walk in each profile, through the real guards and hooks.

### Changed
- `init` and `setup` share one scaffold preview (`init_actions`/`apply_init`), so setup's plan is exactly what gets
  written.
- CODEOWNERS placeholders (`@your-org/...`) no longer count as owners.
- `sdlc setup` checks its arguments before anything else: an unknown option or value, a missing value or
  `--profile=x` is refused (exit 1, nothing written), and `--stack` takes only `python`, `node` or `go` (so does
  `init --stack`).
- An unknown `profile` in `config.json` is a doctor `✗` and stops `setup --dry-run` with the fix, instead of a
  traceback. So does a `config.json` or `settings.json` that isn't a JSON object.
- A write that fails part-way (a link swapped in, a folder in a file's place) is reported with the files already
  written, instead of a traceback.
- Run by the agent, setup prints a `solo` or `strict` profile as the exact terminal command for the human, and a
  rerun with only human-owned changes left says "Nothing for the agent to write".

### Security (fixes from this release's reviews)
- **No sandbox command.** A `--sandbox` trial-repo builder was written during this release and removed before it
  shipped: reviews showed a same-user agent could redirect its git into the calling repo. Setup writes only in the
  repo it runs in.
- **`sdlc init --force` run by the agent keeps human-owned files:** `.aiops/config.json`, `.aiops/config/`,
  `.claude/`, CODEOWNERS and `.github/workflows/`. It lists them for the human, and nothing suggests `--force` to the agent.
- **Scaffold writes never follow a link.** `init` and `setup` refuse when a scaffold file or `.gitignore` has a symlink
  on its path, and every write opens its directories without following links and creates the file anew, so neither a
  symlink nor a hard link can send it to another file, inside or outside the repo.
- **Run by the agent, setup creates `config.json` exactly as `init` does** (team defaults); another profile is printed
  as a human step.
- **`init` and `setup` scaffold only the top of a git repository,** never `$HOME`, `~/.claude` or a folder on PATH,
  and refuse git's `GIT_DIR`/`GIT_WORK_TREE`-style variables and a `CLAUDE_PROJECT_DIR` naming another repo. Home is
  read from the account record too, not only `$HOME`. The pre-bash guard lets the agent run them only in its
  session's repo. Run by the agent, `init --force` keeps every file the guard won't let the agent write (protected
  paths, the read-only lock).
- **Setup never folds an unreviewed human-owned file into your commit.** A file such as `allowed-signers` that
  existed before setup and isn't committed (the agent could have planted a key while the guards were off) is shown as
  `!` with its diff against the template, named in a "review before committing" step, and left out of the commit
  command. That command is `git add -- <files> && git commit … -- <files>`, so it commits exactly the scaffold, never
  `git add -A` and never the rest of the index (a key staged with git plumbing is flagged too). Setup's own files
  from an earlier run aren't flagged, and the commit step is printed on every run. Diffs of content setup didn't
  write escape control characters.
- **Preflight never runs a tool from a PATH folder inside the repo** (an agent could plant one there), runs git by
  its absolute path, and gives the tools it runs no stdin.
- **`no-touch-required` is matched in any letter case** in `allowed-signers`, by doctor, `approve` and the CI audit.
- **`strict` is enforced in CI.** Under `approval_key_policy: "sk"`, the audit requires each approval to be signed by an
  allow-listed `sk-` key without `no-touch-required`, and doctor flags any other allowed signer.
- **The marketplace snippet and install commands are pinned** to the release tag (`ref`, `owner/repo@ref`). README and
  SECURITY.md state what enabling the plugin trusts. Setup compares the snippet's values, so an older ref or a fork
  shows as `!` and is proposed as a change.
- **Setup shows the diffs before you confirm,** dry run included. An invalid-JSON `config.json` or `settings.json`
  stops setup with `✗` instead of being skipped.

### Known issues (planned for 0.2.0-alpha.3)
- **After setup:** a default setup (no `--stack`) ends with doctor's "Makefile contract wired" ✗, and rerunning setup
  with `--stack` can't add the stack once everything else is in place. Wire the recipes by hand for now.
- **Prompts:** Ctrl-D at the profile question shows a traceback, and `--yes` on a terminal without `--profile` still
  asks.
- **Output:**
  - The plan doesn't list `.gitignore`.
  - The "Already set up" path prints no Doctor section.
  - Doctor's profile row can disagree with the actual keys.
  - Under the agent, a requested profile change prints the signing steps of the *current* profile.
- **Tools and paths:** preflight finds `gh` and `claude` through PATH (folders inside the repo are skipped).
  `sdlc feedback` reduces only the repo and home paths.
- **`strict`, unverified:** OpenSSH may not accept `no-touch-required` in `allowed_signers` (it is an
  `authorized_keys` option), so the doctor and CI checks for it may never fire. Whether `ssh-keygen -Y verify`
  enforces the touch on `sk-` signatures needs a FIDO key to test.
- **Errors and help:**
  - A `.gitignore` that isn't UTF-8 stops `init`/`setup` with a traceback, after the scaffold files are written.
  - Under `strict`, the signing help from doctor and `approve` still suggests a passphrase key, which strict refuses
    (setup's own steps say `ed25519-sk`).
  - Run by the agent on a repo that already has a config, the profile human step says "leaves it at init's
    defaults" instead of "leaves it unchanged".
- **Docs and tests:**
  - TROUBLESHOOTING says "human gate" where merge blocks say "final gate".
  - The README's engine and configuration lists miss `setup`, `feedback` and `profile`.
  - The playbook test approves through `approvals.approve`, not through the prompt hook, and AC-15's solo `!` row is
    checked by hand only.
  - The `"sk"` doctor case is covered only through `signing_problem`.
  - The test suite leaves side directories (stub tools, scratch homes) next to its temp repos in `/tmp`.

- **Your first "adopt" commit (review round 9).** Setup leaves unreviewed human-owned files out of the commit step it
  prints, but an agent running as you controls `.git`, so these still get through:
  - A `config.json` planted before `init` with one profile's keys (a downgrade to `solo`, say) passes as setup's own
    file: no `!`, and it is in the commit step.
  - A key staged with git plumbing is flagged, but the review shows the file on disk, not the staged content. Unstage
    it with `git restore --staged -- <file>`.
  - A staged key hidden with `git update-index --skip-worktree` or `--assume-unchanged` isn't flagged, and the printed
    commit step then fails; a plain `git commit` would take the key.
  - Repo-local git config planted before `init` (a `clean` filter, attributes, hooks) can change what the commit step
    commits, and also what `git show`/`git diff` display (textconv, a pager) and what gets pushed (a pre-push hook).

  **Workaround.** Anything that runs in your checkout can be bent by what the agent planted there, including the
  commands you check with. So:
  1. Before running setup in a repo that isn't set up yet, and again before committing, look at `.git` itself:
     `git config --local --list` should have no `filter.*`, `diff.*`, `core.pager`, `core.hooksPath` or
     `core.fsmonitor`; `.git/info/attributes` should be missing or empty; `ls .git/hooks` should show only
     `*.sample` files. Remove anything you didn't put there.
  2. If a staged key won't unstage, run `git update-index --no-skip-worktree --no-assume-unchanged -- <file>` first,
     then `git restore --staged -- <file>`.
  3. After committing, read every commit you are about to push, without repo-local diff drivers or pager:
     `git --no-pager log --stat --patch --no-textconv --no-ext-diff origin/main..HEAD` (`--root` instead of the range in a repo with no remote yet). Check that `.aiops/config.json`
     has the profile you chose and that `allowed-signers` holds only keys you know.
  4. Before merging, read the adoption PR's full "Files changed" on GitHub, every file, ideally with a second person.
     That view doesn't depend on your checkout (a pre-push hook could even push a different commit). CODEOWNERS
     doesn't help here: GitHub reads it from the base branch, and the adoption PR is the one that adds it.
- **Review round 9 (minor):**
  - After a human run merged keys into a committed `settings.json` or `config.json`, a rerun flags that file as "not
    in any commit yet", which is wrong (it is in HEAD, just changed).
  - The commit step also lists uncommitted local edits to scaffold files such as `Makefile` or `CLAUDE.md`.
  - The pre-bash guard refuses a line that only mentions `sdlc init|setup` next to a directory or git-location change
    (`cd`, `pushd`, `-C`, `--chdir`, `-execdir`, `GIT_*=`, `HOME=`, `CLAUDE_PROJECT_DIR=`: a commit message, a
    `grep -C3`), or run from another repo: split the command.
  - The inventory prints the stored profile unescaped, and bidi overrides pass setup's escaping.
- **Review round 8 (low):**
  - The pre-bash guard allows git index plumbing (`hash-object -w`, `update-index --cacheinfo`, `git add`) on
    protected paths such as `allowed-signers`. Setup flags such staged content (see round 9 for the gaps).
  - Doctor's CODEOWNERS ✓ ignores a later rule without owners that uncovers part of `/.aiops/` (CI is unaffected).
  - `init --force`'s secret-paths check (L1) has no test: no default scaffold file matches `secret-paths`.
- **Review round 2 (low):**
  - Doctor misreads `allowed-signers` options quoted with spaces (a quoted value can even hide a key type from the
    strict check). That gives a false ✓ in doctor; CI fails closed.
  - The pin is a tag, not a commit sha.
  - The marketplace merge drops other keys under `zouj`, such as `autoUpdate`.
  - The settings plan note always says "add", even when it replaces an older ref or a fork.
  - An explicit `enabledPlugins: false` is proposed again on every rerun.

### Upgrading from 0.2.0-alpha.1
Nothing changes until you run `sdlc setup`. A config without `profile` reads as `team`. To record your profile, run
`sdlc setup --profile solo|team|strict` in your own terminal and confirm the diff.

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

[Unreleased]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.2.0-alpha.3...HEAD
[0.2.0-alpha.3]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.2.0-alpha.2...v0.2.0-alpha.3
[0.2.0-alpha.2]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.2.0-alpha.1...v0.2.0-alpha.2
[0.2.0-alpha.1]: https://github.com/zoujagger/zouj-ai-sdlc/compare/v0.1.0...v0.2.0-alpha.1
[0.1.0]: https://github.com/zoujagger/zouj-ai-sdlc/releases/tag/v0.1.0
